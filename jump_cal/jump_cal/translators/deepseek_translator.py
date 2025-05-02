import os
from datetime import datetime
from typing import List, Dict
from openai import OpenAI


class DeepSeekTranslator:
    """A translator class that uses DeepSeek API for Japanese to Chinese translation."""
    
    def __init__(self, api_key: str = None, base_url: str = "https://api.deepseek.com"):
        """
        Initialize the DeepSeek translator.
        
        Args:
            api_key (str, optional): DeepSeek API key. If not provided, will try to get from environment.
            base_url (str, optional): DeepSeek API base URL. Defaults to "https://api.deepseek.com".
        """
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable or pass api_key parameter.")
            
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.model = "deepseek-coder"
        self.temperature = 1.3

    def translate_text(self, text: str) -> str:
        """
        Translate a single text from Japanese to Chinese.
        
        Args:
            text (str): Japanese text to translate
            
        Returns:
            str: Translated Chinese text
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that translates Japanese text to Chinese. Please translate the text accurately."},
                    {"role": "user", "content": f"Translate the following text from Japanese to Chinese:\n{text}"}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Translation error: {str(e)}")
            return text

    def batch_translate_texts(self, texts: List[str]) -> List[str]:
        """
        Translate multiple texts from Japanese to Chinese in a single API call.
        
        Args:
            texts (List[str]): List of Japanese texts to translate
            
        Returns:
            List[str]: List of translated Chinese texts
        """
        try:
            # Combine all texts into one prompt with numbering
            combined_text = "\n---\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
            
            print(f"\nSending batch of {len(texts)} texts for translation...")
            print(f"Original texts:\n{combined_text}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that translates Japanese text to Chinese. Please translate each text separately and maintain the numbering. Return only the translations, one per line, with the same numbering."},
                    {"role": "user", "content": f"Translate the following texts from Japanese to Chinese, keeping the same numbering:\n{combined_text}"}
                ]
            )
            
            # Get the response content
            response_text = response.choices[0].message.content.strip()
            print(f"Translation response:\n{response_text}")
            
            # Split the response into individual translations
            translations = []
            for line in response_text.split('\n'):
                # Skip empty lines and separator lines
                if not line.strip() or line.strip() == '---':
                    continue
                    
                # Try to extract the translation
                try:
                    # Handle both formats: "1. translation" or just "translation"
                    if '. ' in line:
                        translation = line.split('. ', 1)[1]
                    else:
                        translation = line
                    translations.append(translation.strip())
                except Exception as e:
                    print(f"Error parsing translation line: {line}")
                    translations.append(line.strip())
            
            # Verify we got the right number of translations
            if len(translations) != len(texts):
                print(f"Warning: Got {len(translations)} translations for {len(texts)} texts")
                # Pad with original texts if we got fewer translations
                while len(translations) < len(texts):
                    translations.append(texts[len(translations)])
            
            print(f"Processed translations:\n{translations}")
            return translations
            
        except Exception as e:
            print(f"Batch translation error: {str(e)}")
            return texts

    def translate_document(self, doc: Dict, fields_to_translate: List[str]) -> Dict:
        """
        Translate specific fields in a document from Japanese to Chinese.
        
        Args:
            doc (Dict): Document containing fields to translate
            fields_to_translate (List[str]): List of field names to translate
            
        Returns:
            Dict: Document with translated fields (original fields remain unchanged)
        """
        translated_doc = doc.copy()
        
        for field in fields_to_translate:
            if field in doc and doc[field]:
                translated_doc[f'{field}CN'] = self.translate_text(doc[field])
        
        return translated_doc

    def batch_translate_documents(self, docs: List[Dict], fields_to_translate: List[str]) -> List[Dict]:
        """
        Translate specific fields in multiple documents from Japanese to Chinese.
        
        Args:
            docs (List[Dict]): List of documents containing fields to translate
            fields_to_translate (List[str]): List of field names to translate
            
        Returns:
            List[Dict]: List of documents with translated fields
        """
        translated_docs = []
        
        # Prepare batches for each field
        for field in fields_to_translate:
            texts_to_translate = []
            doc_indices = []
            
            # Collect all texts for this field
            for i, doc in enumerate(docs):
                if field in doc and doc[field]:
                    texts_to_translate.append(doc[field])
                    doc_indices.append(i)
            
            if texts_to_translate:
                print(f"\nTranslating {len(texts_to_translate)} {field} fields...")
                translations = self.batch_translate_texts(texts_to_translate)
                
                # Apply translations back to documents
                for idx, translation in zip(doc_indices, translations):
                    if idx >= len(translated_docs):
                        translated_docs.append(docs[idx].copy())
                    translated_docs[idx][f'{field}CN'] = translation
        
        # Verify translations
        for doc in translated_docs:
            translation_performed = False
            for field in fields_to_translate:
                if f'{field}CN' in doc and doc[f'{field}CN'] != doc[field]:
                    translation_performed = True
                    break
            
            if not translation_performed:
                raise ValueError(f"No translation was performed for document {doc['_id']}")
        
        return translated_docs 