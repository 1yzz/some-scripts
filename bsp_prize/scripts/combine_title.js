const fs = require('fs')
const path = require('path')

const cnFilePath = path.join(__dirname, '../build/data/bsp_item_title_cn.json');
const jpFilePath = path.join(__dirname, '../build/data/bsp_item_title_jp.json');
const itemAllFilePath = path.join(__dirname, '../build/data/bsp_item_all.json');
const outputFilePath = path.join(__dirname, '../build/bsp_item_all_title_translated.json');

const cnData = JSON.parse(fs.readFileSync(cnFilePath, 'utf8'));
const jpData = JSON.parse(fs.readFileSync(jpFilePath, 'utf8'));
const itemAllData = JSON.parse(fs.readFileSync(itemAllFilePath, 'utf8'));


if (cnData.length !== jpData.length) {
    console.error('cn and jp length mismatch!');
    process.exit(1);
}

const combinedData = itemAllData.map((item, index) => {
    if (item.title ===jpData[index]) {
        item.title_cn = cnData[index];
        console.log('Mathed title:', item.title);
    } else {
        console.error('Mismatched title:', item.title, cnData[index]);
    }
    return {
        ...item,
    }
});


fs.writeFileSync(outputFilePath, JSON.stringify(combinedData), 'utf8');

console.log('Files have been combined and saved to', outputFilePath);