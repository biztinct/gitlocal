const ExcelJS = require('exceljs');
const fs = require('fs');

async function copyValues(inputPath, outputPath) {
    console.log("JavaScript function is being called!");

    const workbook = new ExcelJS.Workbook();
    try {
        await workbook.xlsx.readFile(inputPath);
    } catch (error) {
        console.error("Error reading the input file:", error);
        process.exit(1); // Exit with an error code
    }

    const stagingSheet = workbook.getWorksheet('Staging');
    const finalSheet = workbook.getWorksheet('Final');

    if (!stagingSheet || !finalSheet) {
        console.error("Staging or Final sheet not found.");
        process.exit(1); // Exit with an error code
    }

    // Copy values from Staging to Final
    stagingSheet.eachRow((row, rowNumber) => {
        row.eachCell((cell, colNumber) => {
            const value = cell.value; // Get the visible value from Staging cell
            const finalCell = finalSheet.getCell(rowNumber, colNumber);
            finalCell.value = value; // Update Final cell with the value
        });
    });

    try {
        await workbook.xlsx.writeFile(outputPath);
    } catch (error) {
        console.error("Error writing the output file:", error);
        process.exit(1); // Exit with an error code
    }
    console.log("Values copied successfully!");
}

const inputPath = process.argv[2]; // Get the input path from command line arguments
const outputPath = process.argv[3]; // Get the output path from command line arguments

copyValues(inputPath, outputPath)
    .then(() => console.log('Done'))
    .catch(error => console.error('Error:', error));