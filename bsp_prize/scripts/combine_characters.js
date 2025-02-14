const fs = require('fs')
const path = require('path')

const args = process.argv.slice(2); // Slice off the first two elements (node and script path)

console.log("Arguments passed:", args);

if (!args[0]) {
    console.error('Sepcify Input file path!')
    process.exit(0)
}


const itemAllFilePath = path.join(__dirname, args[0]);
const cnFilePath = path.join(__dirname, '../build/data/bsp_item_characters-translated.json');


const outputFilePath = path.join(__dirname, `../build/bsp_item_all__translated_title_character_${Date.now()}.json`);

const cnData = JSON.parse(fs.readFileSync(cnFilePath, 'utf8'));

const itemAllData = JSON.parse(fs.readFileSync(itemAllFilePath, 'utf8'));


const combinedData = itemAllData.map((item, index) => {
    return {
        ...item,
        characters: item.characters.map((character) => {
            const matchedCharacter = cnData.find((cnCharacter) => cnCharacter.jp === character);
            if (matchedCharacter) {
                return matchedCharacter
            } else {
                console.error('Character not found:', character);
                return {
                    jp: character,
                }
            }
        })
    }
});


fs.writeFileSync(outputFilePath, JSON.stringify(combinedData), 'utf8');

console.log('Files have been combined and saved to', outputFilePath);