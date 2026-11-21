const { topbarMenuRegistry } = spreadsheet.registries;
const uuidGenerator = new spreadsheet.helpers.UuidGenerator();

topbarMenuRegistry.add("file", { name: _t("File"), sequence: 10 });

topbarMenuRegistry.addChild("copy_sheet_as_values", ["file"], {
    name: _t("Copy Sheet as Values"),
    sequence: 30, // Position the menu item appropriately
    action: (env) => {
        const spreadsheetInstance = spreadsheet.getActiveSpreadsheet();
        if (!spreadsheetInstance) {
            console.warn("No active spreadsheet found.");
            return;
        }

        const activeSheetName = spreadsheetInstance.getActiveSheetName();
        const activeSheetData = spreadsheetInstance.getSheetData(activeSheetName);

        if (!activeSheetData) {
            console.warn("No active sheet data found.");
            return;
        }

        const newSheetName = `${activeSheetName}_CopyAsValues`;
        spreadsheetInstance.addSheet(newSheetName);
        const newSheet = spreadsheetInstance.getSheetData(newSheetName);

        if (!newSheet) {
            console.warn("Failed to create new sheet.");
            return;
        }

        // Copy only values, not formulas
        for (let rowIndex = 0; rowIndex < activeSheetData.length; rowIndex++) {
            for (let colIndex = 0; colIndex < activeSheetData[rowIndex].length; colIndex++) {
                const cell = activeSheetData[rowIndex][colIndex];
                const value = cell && cell.value ? cell.value : null; 
                newSheet.setCell(rowIndex, colIndex, value);
            }
        }

        console.log(`Active sheet "${activeSheetName}" copied as values to the new sheet "${newSheetName}".`);
    },
});
