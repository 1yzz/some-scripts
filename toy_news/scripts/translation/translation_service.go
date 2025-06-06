package main

import (
	"bytes"
	"context"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"syscall"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// TranslationService represents the main translation service
type TranslationService struct {
	mongoURI          string
	mongoDB           string
	mongoCollection   string
	checkInterval     int
	translator        *DeepSeekTranslator
	batchSize         int
	running           bool
	fieldsToTranslate []string

	// MongoDB collections
	client               *mongo.Client
	db                   *mongo.Database
	normalizedCollection *mongo.Collection
	pendingCollection    *mongo.Collection
	cacheCollection      *mongo.Collection
}

// PendingItem represents a pending translation item
type PendingItem struct {
	ID          primitive.ObjectID `bson:"_id,omitempty"`
	ProductHash string             `bson:"product_hash"`
	Name        string             `bson:"name,omitempty"`
	Description string             `bson:"description,omitempty"`
	CreatedAt   time.Time          `bson:"createdAt"`
}

// TranslatedItem represents an item with translations
type TranslatedItem struct {
	PendingItem
	NameCN        string `bson:"nameCN,omitempty"`
	DescriptionCN string `bson:"descriptionCN,omitempty"`
}

// CacheItem represents a cached translation
type CacheItem struct {
	ID             primitive.ObjectID `bson:"_id,omitempty"`
	TextHash       string             `bson:"text_hash"`
	OriginalText   string             `bson:"original_text"`
	TranslatedText string             `bson:"translated_text"`
	CreatedAt      time.Time          `bson:"created_at"`
	UpdatedAt      time.Time          `bson:"updated_at"`
	UsageCount     int                `bson:"usage_count"`
}

// UpdateOperation represents a bulk update operation
type UpdateOperation struct {
	ProductHash string
	Updates     bson.M
}

// DeepSeekTranslator represents the DeepSeek API translator
type DeepSeekTranslator struct {
	apiKey      string
	baseURL     string
	model       string
	temperature float64
}

// ChatCompletionRequest represents the OpenAI-compatible chat completion request
type ChatCompletionRequest struct {
	Model       string    `json:"model"`
	Temperature float64   `json:"temperature"`
	Messages    []Message `json:"messages"`
}

// Message represents a chat message
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatCompletionResponse represents the API response
type ChatCompletionResponse struct {
	Choices []Choice `json:"choices"`
}

// Choice represents a response choice
type Choice struct {
	Message Message `json:"message"`
}

// NewDeepSeekTranslator creates a new DeepSeek translator
func NewDeepSeekTranslator() *DeepSeekTranslator {
	apiKey := os.Getenv("DEEPSEEK_API_KEY")
	if apiKey == "" {
		log.Fatal("DEEPSEEK_API_KEY environment variable is required")
	}

	return &DeepSeekTranslator{
		apiKey:      apiKey,
		baseURL:     "https://api.deepseek.com",
		model:       "deepseek-coder",
		temperature: 1.3,
	}
}

// callAPI makes the actual HTTP request to DeepSeek API
func (dt *DeepSeekTranslator) callAPI(req ChatCompletionRequest) (string, error) {
	// Marshal request to JSON
	jsonData, err := json.Marshal(req)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	url := dt.baseURL + "/chat/completions"
	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create HTTP request: %w", err)
	}

	// Set headers
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+dt.apiKey)

	// Create HTTP client with timeout
	client := &http.Client{
		Timeout: 60 * time.Second,
	}

	// Make the request
	resp, err := client.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("failed to make HTTP request: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response body: %w", err)
	}

	// Check status code
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(body))
	}

	// Parse JSON response
	var response ChatCompletionResponse
	err = json.Unmarshal(body, &response)
	if err != nil {
		return "", fmt.Errorf("failed to unmarshal response: %w", err)
	}

	// Extract content from response
	if len(response.Choices) == 0 {
		return "", fmt.Errorf("no choices in API response")
	}

	return response.Choices[0].Message.Content, nil
}

// TranslateTexts translates multiple texts in batch
func (dt *DeepSeekTranslator) TranslateTexts(texts []string) ([]string, error) {
	if len(texts) == 0 {
		return []string{}, nil
	}

	// Log original texts being sent to API
	log.Printf("📋 发送给API的原始文本 (共%d条):", len(texts))
	for i, text := range texts {
		log.Printf("  %d. %s", i+1, text)
	}

	// Combine texts with numbering
	var combinedParts []string
	for i, text := range texts {
		combinedParts = append(combinedParts, fmt.Sprintf("%d. %s", i+1, text))
	}
	combinedText := strings.Join(combinedParts, "\n---\n")

	log.Printf("⏳ 正在调用DeepSeek API翻译 %d 个文本...", len(texts))

	// Create request
	req := ChatCompletionRequest{
		Model:       dt.model,
		Temperature: dt.temperature,
		Messages: []Message{
			{
				Role:    "system",
				Content: "You are a helpful assistant that translates Japanese text to Chinese. Please translate each text separately and maintain the numbering. Return only the translations, one per line, with the same numbering format: '1. translation', '2. translation', etc.",
			},
			{
				Role:    "user",
				Content: fmt.Sprintf("Translate the following texts from Japanese to Chinese, keeping the same numbering format:\n%s", combinedText),
			},
		},
	}

	// Make API call
	response, err := dt.callAPI(req)
	if err != nil {
		log.Printf("Translation API error: %v", err)
		return texts, err // Return original texts on error
	}

	// Parse response
	translations := dt.parseTranslations(response, len(texts))

	// Validate translation count
	if len(translations) != len(texts) {
		log.Printf("Warning: Got %d translations for %d texts", len(translations), len(texts))

		// Fix mismatched counts
		if len(translations) > len(texts) {
			translations = translations[:len(texts)]
		} else {
			for len(translations) < len(texts) {
				missingIndex := len(translations)
				translations = append(translations, texts[missingIndex])
			}
		}
	}

	return translations, nil
}

// parseTranslations parses the API response into individual translations
func (dt *DeepSeekTranslator) parseTranslations(response string, expectedCount int) []string {
	var translations []string
	lines := strings.Split(strings.TrimSpace(response), "\n")

	// Regex to match numbered lines
	numberRegex := regexp.MustCompile(`^(\d+)\.\s*(.+)$`)

	for _, line := range lines {
		line = strings.TrimSpace(line)

		// Skip empty lines and separators
		if line == "" || line == "---" {
			continue
		}

		// Match numbered lines
		matches := numberRegex.FindStringSubmatch(line)
		if len(matches) == 3 {
			translation := strings.TrimSpace(matches[2])
			if translation != "" {
				translations = append(translations, translation)
			} else {
				log.Printf("Warning: Empty translation for line: %s", line)
			}
		} else {
			log.Printf("Warning: Skipping non-numbered line: %s", line)
		}
	}

	return translations
}

// NewTranslationService creates a new translation service instance
func NewTranslationService(mongoURI, mongoDB, mongoCollection string, checkInterval int) *TranslationService {
	return &TranslationService{
		mongoURI:          mongoURI,
		mongoDB:           mongoDB,
		mongoCollection:   mongoCollection,
		checkInterval:     checkInterval,
		translator:        NewDeepSeekTranslator(),
		batchSize:         20,
		running:           true,
		fieldsToTranslate: []string{"name", "description"},
	}
}

// ConnectMongoDB establishes MongoDB connection
func (ts *TranslationService) ConnectMongoDB(ctx context.Context) error {
	clientOptions := options.Client().ApplyURI(ts.mongoURI)
	client, err := mongo.Connect(ctx, clientOptions)
	if err != nil {
		return fmt.Errorf("failed to connect to MongoDB: %w", err)
	}

	// Test connection
	err = client.Ping(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to ping MongoDB: %w", err)
	}

	ts.client = client
	ts.db = client.Database(ts.mongoDB)
	ts.normalizedCollection = ts.db.Collection(ts.mongoCollection)
	ts.pendingCollection = ts.db.Collection("toys_translation_pending")
	ts.cacheCollection = ts.db.Collection("toys_translation_cache")

	// Create indexes
	err = ts.createIndexes(ctx)
	if err != nil {
		return fmt.Errorf("failed to create indexes: %w", err)
	}

	log.Println("Connected to MongoDB successfully")
	return nil
}

// createIndexes creates necessary MongoDB indexes
func (ts *TranslationService) createIndexes(ctx context.Context) error {
	// Create cache index
	indexModel := mongo.IndexModel{
		Keys:    bson.D{{"text_hash", 1}},
		Options: options.Index().SetUnique(true),
	}
	_, err := ts.cacheCollection.Indexes().CreateOne(ctx, indexModel)
	if err != nil {
		return fmt.Errorf("failed to create cache index: %w", err)
	}

	return nil
}

// CloseMongoDB closes the MongoDB connection
func (ts *TranslationService) CloseMongoDB(ctx context.Context) error {
	if ts.client != nil {
		return ts.client.Disconnect(ctx)
	}
	return nil
}

// GetTextHash generates MD5 hash of text
func (ts *TranslationService) GetTextHash(text string) string {
	hash := md5.Sum([]byte(text))
	return hex.EncodeToString(hash[:])
}

// GetCachedTranslation retrieves translation from cache
func (ts *TranslationService) GetCachedTranslation(ctx context.Context, text string) (string, error) {
	textHash := ts.GetTextHash(text)

	var cached CacheItem
	err := ts.cacheCollection.FindOne(ctx, bson.M{"text_hash": textHash}).Decode(&cached)
	if err != nil {
		if err == mongo.ErrNoDocuments {
			return "", nil // Not found
		}
		return "", err
	}

	return cached.TranslatedText, nil
}

// CacheTranslation stores translation in cache
func (ts *TranslationService) CacheTranslation(ctx context.Context, originalText, translatedText string) error {
	textHash := ts.GetTextHash(originalText)
	now := time.Now()

	// Try to update existing cache entry
	filter := bson.M{"text_hash": textHash}
	update := bson.M{
		"$setOnInsert": bson.M{"created_at": now},
		"$set": bson.M{
			"text_hash":       textHash,
			"original_text":   originalText,
			"translated_text": translatedText,
			"updated_at":      now,
			"usage_count":     1,
		},
	}

	opts := options.Update().SetUpsert(true)
	result, err := ts.cacheCollection.UpdateOne(ctx, filter, update, opts)
	if err != nil {
		return err
	}

	// If it was an update (not insert), increment usage count
	if result.UpsertedID == nil {
		incUpdate := bson.M{
			"$inc": bson.M{"usage_count": 1},
			"$set": bson.M{"updated_at": now},
		}
		_, err = ts.cacheCollection.UpdateOne(ctx, filter, incUpdate)
		if err != nil {
			return err
		}
	}

	return nil
}

// TranslateWithCache translates items using cache
func (ts *TranslationService) TranslateWithCache(ctx context.Context, items []PendingItem) ([]TranslatedItem, error) {
	// Convert to translated items
	translatedItems := make([]TranslatedItem, len(items))
	for i, item := range items {
		translatedItems[i] = TranslatedItem{PendingItem: item}
	}

	translationMap := make(map[string]map[string][]int) // field -> text -> item_indices
	cacheHits := 0
	cacheMisses := 0

	// Check cache for each item
	for i := range translatedItems {
		item := &translatedItems[i]

		// Log the pending item details
		log.Printf("📝 处理项目 %d - ProductHash: %s", i+1, item.ProductHash)

		for _, field := range ts.fieldsToTranslate {
			var originalText string
			switch field {
			case "name":
				originalText = item.Name
			case "description":
				originalText = item.Description
			}

			if originalText != "" {
				log.Printf("  🔤 需要翻译的%s: %s", field, originalText)

				cachedTranslation, err := ts.GetCachedTranslation(ctx, originalText)
				if err != nil {
					log.Printf("Error getting cached translation: %v", err)
					continue
				}

				if cachedTranslation != "" {
					// Cache hit - set translation directly
					log.Printf("  ✅ 缓存命中 %s: %s", field, cachedTranslation)
					switch field {
					case "name":
						item.NameCN = cachedTranslation
					case "description":
						item.DescriptionCN = cachedTranslation
					}
					cacheHits++
				} else {
					// Cache miss - add to translation map
					log.Printf("  ❌ 缓存未命中 %s，需要API翻译", field)
					if translationMap[field] == nil {
						translationMap[field] = make(map[string][]int)
					}
					if translationMap[field][originalText] == nil {
						translationMap[field][originalText] = []int{}
					}
					translationMap[field][originalText] = append(
						translationMap[field][originalText],
						i,
					)
					cacheMisses++
				}
			}
		}
	}

	log.Printf("Cache hits: %d, Cache misses: %d", cacheHits, cacheMisses)

	// Translate uncached texts
	for field, textMap := range translationMap {
		if len(textMap) == 0 {
			continue
		}

		// Prepare texts for batch translation
		var textsToTranslate []string
		var textOrder []string

		for text := range textMap {
			textsToTranslate = append(textsToTranslate, text)
			textOrder = append(textOrder, text)
		}

		log.Printf("Translating %d unique %s texts...", len(textsToTranslate), field)

		// 打印即将翻译的文本列表
		log.Printf("🚀 准备批量翻译 %s 字段，共 %d 个文本:", field, len(textsToTranslate))
		for i, text := range textsToTranslate {
			log.Printf("  [%d] %s", i+1, text)
		}
		log.Printf("📤 发送到DeepSeek API...")

		// Batch translate
		translations, err := ts.translator.TranslateTexts(textsToTranslate)
		if err != nil {
			log.Printf("Error translating texts: %v", err)
			continue
		}

		// Process translation results
		for i, translation := range translations {
			if i >= len(textOrder) {
				break
			}

			originalText := textOrder[i]

			// Cache the translation
			err = ts.CacheTranslation(ctx, originalText, translation)
			if err != nil {
				log.Printf("Error caching translation: %v", err)
			}

			// Update items with translation
			itemIndices := textMap[originalText]
			for _, itemIndex := range itemIndices {
				switch field {
				case "name":
					translatedItems[itemIndex].NameCN = translation
				case "description":
					translatedItems[itemIndex].DescriptionCN = translation
				}
			}
		}

		// Log translation results
		log.Printf("=== TRANSLATION RESULTS for %s ===", field)
		for i, translation := range translations {
			if i < len(textOrder) {
				log.Printf("Translation %d: %s -> %s", i+1, textOrder[i], translation)
			}
		}
		log.Printf("=== END TRANSLATION RESULTS ===")

		log.Printf("✅ %s字段翻译完成，结果对比:", field)
		for i, translation := range translations {
			if i < len(textOrder) {
				log.Printf("  原文: %s", textOrder[i])
				log.Printf("  译文: %s", translation)
				log.Printf("  ---")
			}
		}
	}

	return translatedItems, nil
}

// ProcessPendingTranslations processes the translation queue
func (ts *TranslationService) ProcessPendingTranslations(ctx context.Context) (int, error) {
	// Check pending count
	pendingCount, err := ts.pendingCollection.CountDocuments(ctx, bson.M{})
	if err != nil {
		return 0, fmt.Errorf("error counting pending items: %w", err)
	}

	if pendingCount == 0 {
		return 0, nil
	}

	log.Printf("Found %d pending items", pendingCount)

	// Get batch of pending items
	opts := options.Find().SetSort(bson.D{{"createdAt", 1}}).SetLimit(int64(ts.batchSize))
	cursor, err := ts.pendingCollection.Find(ctx, bson.M{}, opts)
	if err != nil {
		return 0, fmt.Errorf("error finding pending items: %w", err)
	}
	defer cursor.Close(ctx)

	var pendingItems []PendingItem
	err = cursor.All(ctx, &pendingItems)
	if err != nil {
		return 0, fmt.Errorf("error decoding pending items: %w", err)
	}

	if len(pendingItems) == 0 {
		return 0, nil
	}

	log.Printf("Processing %d items with cache...", len(pendingItems))

	// Translate with cache
	translatedItems, err := ts.TranslateWithCache(ctx, pendingItems)
	if err != nil {
		return 0, fmt.Errorf("error translating items: %w", err)
	}

	// Prepare bulk operations
	var updateOps []UpdateOperation
	var pendingDeletions []string

	for _, item := range translatedItems {
		updates := bson.M{}
		hasTranslation := false

		// Check for translations and prepare updates
		if item.NameCN != "" {
			updates["nameCN"] = item.NameCN
			hasTranslation = true
		}
		if item.DescriptionCN != "" {
			updates["descriptionCN"] = item.DescriptionCN
			hasTranslation = true
		}

		if hasTranslation {
			updateOps = append(updateOps, UpdateOperation{
				ProductHash: item.ProductHash,
				Updates:     updates,
			})
			pendingDeletions = append(pendingDeletions, item.ProductHash)
		}
	}

	// Execute bulk operations
	if len(updateOps) > 0 {
		var bulkOps []mongo.WriteModel
		for _, op := range updateOps {
			filter := bson.M{"product_hash": op.ProductHash}
			update := bson.M{
				"$set":         op.Updates,
				"$currentDate": bson.M{"updatedAt": true},
			}
			bulkOps = append(bulkOps, mongo.NewUpdateOneModel().SetFilter(filter).SetUpdate(update))
		}

		bulkResult, err := ts.normalizedCollection.BulkWrite(ctx, bulkOps)
		if err != nil {
			return 0, fmt.Errorf("error executing bulk write: %w", err)
		}

		log.Printf("Updated %d products in %s", bulkResult.ModifiedCount, ts.mongoCollection)
	}

	// Remove processed items from pending collection
	if len(pendingDeletions) > 0 {
		filter := bson.M{"product_hash": bson.M{"$in": pendingDeletions}}
		deleteResult, err := ts.pendingCollection.DeleteMany(ctx, filter)
		if err != nil {
			return 0, fmt.Errorf("error deleting pending items: %w", err)
		}

		log.Printf("Removed %d items from translation_pending", deleteResult.DeletedCount)
	}

	return len(pendingDeletions), nil
}

// ShowStats displays service statistics
func (ts *TranslationService) ShowStats(ctx context.Context) error {
	// Pending translations count
	pendingCount, err := ts.pendingCollection.CountDocuments(ctx, bson.M{})
	if err != nil {
		return fmt.Errorf("error counting pending items: %w", err)
	}
	fmt.Printf("Translation pending: %d items\n", pendingCount)

	// Translated products count
	translatedFilter := bson.M{
		"$or": []bson.M{
			{"nameCN": bson.M{"$exists": true}},
			{"descriptionCN": bson.M{"$exists": true}},
		},
	}
	translatedCount, err := ts.normalizedCollection.CountDocuments(ctx, translatedFilter)
	if err != nil {
		return fmt.Errorf("error counting translated items: %w", err)
	}

	totalProducts, err := ts.normalizedCollection.CountDocuments(ctx, bson.M{})
	if err != nil {
		return fmt.Errorf("error counting total products: %w", err)
	}

	fmt.Printf("Translated products: %d/%d\n", translatedCount, totalProducts)

	// Cache statistics
	totalCached, err := ts.cacheCollection.CountDocuments(ctx, bson.M{})
	if err != nil {
		return fmt.Errorf("error counting cache items: %w", err)
	}

	if totalCached > 0 {
		// Aggregate total usage
		pipeline := bson.A{
			bson.M{
				"$group": bson.M{
					"_id":         nil,
					"total_usage": bson.M{"$sum": "$usage_count"},
				},
			},
		}

		cursor, err := ts.cacheCollection.Aggregate(ctx, pipeline)
		if err != nil {
			return fmt.Errorf("error aggregating cache usage: %w", err)
		}
		defer cursor.Close(ctx)

		var result []bson.M
		err = cursor.All(ctx, &result)
		if err != nil {
			return fmt.Errorf("error decoding cache usage: %w", err)
		}

		var totalUsage int64 = totalCached
		if len(result) > 0 && result[0]["total_usage"] != nil {
			if usage, ok := result[0]["total_usage"].(int64); ok {
				totalUsage = usage
			}
		}

		fmt.Printf("Translation cache: %d entries, %d total uses\n", totalCached, totalUsage)
	}

	return nil
}

// Run starts the translation service
func (ts *TranslationService) Run(ctx context.Context) error {
	log.Println("Starting Unified Translation Service...")
	log.Printf("Processing translations for %s collection", ts.mongoCollection)
	log.Printf("Check interval: %d seconds", ts.checkInterval)
	log.Printf("Batch size: %d", ts.batchSize)
	log.Printf("Fields to translate: %v", ts.fieldsToTranslate)
	log.Println()

	// Connect to MongoDB
	err := ts.ConnectMongoDB(ctx)
	if err != nil {
		return fmt.Errorf("failed to connect to MongoDB: %w", err)
	}
	defer ts.CloseMongoDB(ctx)

	// Show initial stats
	err = ts.ShowStats(ctx)
	if err != nil {
		log.Printf("Error showing initial stats: %v", err)
	}
	log.Println()

	// Setup signal handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	ticker := time.NewTicker(time.Duration(ts.checkInterval) * time.Second)
	defer ticker.Stop()

	for ts.running {
		select {
		case <-sigChan:
			log.Println("Received shutdown signal, shutting down gracefully...")
			ts.running = false
			return nil

		case <-ticker.C:
			processed, err := ts.ProcessPendingTranslations(ctx)
			if err != nil {
				log.Printf("Error processing pending translations: %v", err)
				continue
			}

			if processed > 0 {
				log.Printf("Processed %d items in this cycle", processed)
				// Show updated stats
				err = ts.ShowStats(ctx)
				if err != nil {
					log.Printf("Error showing stats: %v", err)
				}
			} else {
				now := time.Now().Format("15:04:05")
				log.Printf("[%s] No pending translations found", now)
			}
		}
	}

	return nil
}

func main() {
	// Command line flags
	var (
		interval        = flag.Int("interval", 10, "Check interval in seconds")
		mongoURI        = flag.String("mongo-uri", "mongodb://localhost:27017/", "MongoDB URI")
		mongoDB         = flag.String("mongo-db", "scrapy_items", "MongoDB database")
		mongoCollection = flag.String("mongo-collection", "toys_normalized", "MongoDB collection")
		showStats       = flag.Bool("show-stats", false, "Show statistics and exit")
	)
	flag.Parse()

	// URL encode the MongoDB URI if it contains special characters
	encodedURI := *mongoURI
	if strings.Contains(encodedURI, "://") {
		parts := strings.SplitN(encodedURI, "://", 2)
		if len(parts) == 2 {
			// Encode the userinfo part (username:password)
			userinfo := strings.SplitN(parts[1], "@", 2)
			if len(userinfo) == 2 {
				// Split username and password
				auth := strings.SplitN(userinfo[0], ":", 2)
				if len(auth) == 2 {
					// Encode username and password separately
					username := url.QueryEscape(auth[0])
					password := url.QueryEscape(auth[1])
					encodedUserinfo := username + ":" + password
					encodedURI = parts[0] + "://" + encodedUserinfo + "@" + userinfo[1]
				}
			}
		}
	}

	// Create service instance
	service := NewTranslationService(encodedURI, *mongoDB, *mongoCollection, *interval)

	ctx := context.Background()

	if *showStats {
		// Only show statistics
		err := service.ConnectMongoDB(ctx)
		if err != nil {
			log.Fatalf("Failed to connect to MongoDB: %v", err)
		}
		defer service.CloseMongoDB(ctx)

		err = service.ShowStats(ctx)
		if err != nil {
			log.Fatalf("Error showing stats: %v", err)
		}
		return
	}

	fmt.Println("Unified Translation Service Configuration:")
	fmt.Printf("  Source: toys_translation_pending -> %s\n", *mongoCollection)
	fmt.Printf("  Fields: %v\n", service.fieldsToTranslate)
	fmt.Println()

	// Run service
	err := service.Run(ctx)
	if err != nil {
		log.Fatalf("Service error: %v", err)
	}

	log.Println("Shutting down Translation Service...")
}
