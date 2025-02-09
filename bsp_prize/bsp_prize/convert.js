const fs = require('fs')
const path = require('path')
const excel = require('exceljs');
const translate = require('@iamtraction/google-translate');

const args = process.argv.slice(2); // Slice off the first two elements (node and script path)

console.log("Arguments passed:", args);

if (!args[0]) {
    console.error('Sepcify Input file path!')
    process.exit(0)
}

const main = () => {
    const inputFile = path.join(process.cwd(), args[0])
    const inputJson = require(inputFile);

    const data = inputJson.map(item => {
        const { thumbs, gallery, date, ...rest } = item
        return item.characters        
    })

    
    fs.writeFileSync(inputFile.replace('.json', `-simple-${Date.now()}.json`), JSON.stringify(data), 'utf8');

    // Or, write JSON file (synchronous)
    // fs.writeFileSync(inputFile.replace('.json', `-simple-${Date.now()}.json`), JSON.stringify(data), 'utf8');
    // console.log('Data written to file (sync)');

    // async function jsonToExcel(jsonData, filename = 'output.xlsx') {
    //     const workbook = new excel.Workbook();
    //     const worksheet = workbook.addWorksheet('Sheet 1');

    //     // Add headers (first row) dynamically from the first object's keys
    //     if (jsonData.length > 0) {
    //         const headers = Object.keys(jsonData[0]);
    //         worksheet.addRow(headers);

    //         // Add data rows
    //         jsonData.forEach(item => {
    //             const values = headers.map(header => item[header]); // Ensure correct order
    //             worksheet.addRow(values);
    //         });
    //     }

    //     try {
    //         await workbook.xlsx.writeFile(filename);
    //         console.log(`JSON to Excel conversion complete! File saved as ${filename}`);
    //     } catch (error) {
    //         console.error('Error writing Excel file:', error);
    //     }
    // }

    // // Example usage (you can use transformedData here too):
    // jsonToExcel(data);

}

main()