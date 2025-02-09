const fs = require('fs')
const path = require('path')
const translate = require('@iamtraction/google-translate');


const itemAllFilePath = path.join(__dirname, '../build/data/bsp_item_all.json');
const jpFilePath = path.join(__dirname, '../build/data/bsp_item_character_jp.json');
const cnFilePath = path.join(__dirname, '../build/bsp_item_all_characters.json');

const outputFilePath = cnFilePath;

const itemAllData = JSON.parse(fs.readFileSync(itemAllFilePath, 'utf8'));
const jpData = JSON.parse(fs.readFileSync(jpFilePath, 'utf8'));



if (jpData.length !== itemAllData.length) {
    console.error('characters and data length mismatch!', jpData.length, itemAllData.length);
    process.exit(1);
}

const allCharacters = new Set();

jpData.forEach(item => {
    item.forEach(character => {
        allCharacters.add(character);
    });
});

console.log('All characters:', allCharacters);


const allCharactersArray = Array.from(allCharacters);

console.log('All characters:', allCharactersArray.length);


fs.writeFileSync(outputFilePath, JSON.stringify(allCharactersArray), 'utf8');

console.log('Files have been combined and saved to', outputFilePath);