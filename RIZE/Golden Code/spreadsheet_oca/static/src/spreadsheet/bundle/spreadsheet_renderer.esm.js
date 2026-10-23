/** @odoo-module **/

import {Component} from "@odoo/owl";
import {DataSources} from "@spreadsheet/data_sources/data_sources";
import Dialog from "web.OwlDialog";
import {Field} from "@web/views/fields/field";
import {loadSpreadsheetDependencies} from "@spreadsheet/helpers/helpers";
import {migrate} from "@spreadsheet/o_spreadsheet/migration";
import spreadsheet from "@spreadsheet/o_spreadsheet/o_spreadsheet_extended";
import {useService} from "@web/core/utils/hooks";
import {useSetupAction} from "@web/webclient/actions/action_hook";
import {waitForDataLoaded} from "@spreadsheet/actions/spreadsheet_download_action";

const {Spreadsheet, Model} = spreadsheet;
const {useSubEnv, useState, onWillStart} = owl;
const uuidGenerator = new spreadsheet.helpers.UuidGenerator();

/** Biztinct spinner functions */
function showSpinner() {
    const spinner = document.createElement("div");
    spinner.id = "loading-spinner";
    spinner.style.position = "fixed";
    spinner.style.top = "0";
    spinner.style.left = "0";
    spinner.style.width = "100%";
    spinner.style.height = "100%";
    spinner.style.backgroundColor = "rgba(0, 0, 0, 0.5)";
    spinner.style.zIndex = "9999";
    spinner.style.display = "flex";
    spinner.style.justifyContent = "center";
    spinner.style.alignItems = "center";
    spinner.innerHTML = `
        <div style="
            border: 8px solid #f3f3f3;
            border-top: 8px solid #3498db;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
        "></div>
        <style>
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    `;
    document.body.appendChild(spinner); // Add spinner to the DOM
}

function hideSpinner() {
    const spinner = document.getElementById("loading-spinner");
    if (spinner) {
        document.body.removeChild(spinner); // Remove spinner from the DOM
    }
}
/** Biztinct ends  */

class SpreadsheetTransportService {
    constructor(orm, bus_service, model, res_id) {
        this.orm = orm;
        this.bus_service = bus_service;
        this.model = model;
        this.res_id = res_id;
        this.channel = "spreadsheet_oca;" + this.model + ";" + this.res_id;
        this.bus_service.addChannel(this.channel);
        this.bus_service.addEventListener(
            "notification",
            this.onNotification.bind(this)
        );
        this.listeners = [];
    }
    onNotification({detail: notifications}) {
        for (const {payload, type} of notifications) {
            if (
                type === "spreadsheet_oca" &&
                payload.res_model === this.model &&
                payload.res_id === this.res_id
            ) {
                // What shall we do if no callback is defined (empty until onNewMessage...) :/
                for (const {callback} of this.listeners) {
                    callback(payload);
                }
            }
        }
    }
    sendMessage(message) {
        this.orm.call(this.model, "send_spreadsheet_message", [[this.res_id], message]);
    }
    onNewMessage(id, callback) {
        this.listeners.push({id, callback});
    }
    leave(id) {
        this.listeners = this.listeners.filter((listener) => listener.id !== id);
    }
}

export class SpreadsheetRenderer extends Component {
    setup() {
        this.orm = useService("orm");
        this.bus_service = useService("bus_service");
        this.user = useService("user");
        this.ui = useService("ui");
        this.action = useService("action");
        const dataSources = new DataSources(this.orm);
        this.state = useState({
            dialogDisplayed: false,
            dialogTitle: "Spreadsheet",
            dialogContent: undefined,
        });
        this.confirmDialog = this.closeDialog;
        this.spreadsheet_model = new Model(
            migrate(this.props.record.spreadsheet_raw),
            {
                evalContext: {env: this.env, orm: this.orm},
                transportService: new SpreadsheetTransportService(
                    this.orm,
                    this.bus_service,
                    this.props.model,
                    this.props.res_id
                ),
                client: {
                    id: uuidGenerator.uuidv4(),
                    name: this.user.name,
                },
                mode: this.props.record.mode,
                dataSources,
            },
            this.props.record.revisions
        );
        useSubEnv({
            saveSpreadsheet: this.onSpreadsheetSaved.bind(this),
            editText: this.editText.bind(this),
            askConfirmation: this.askConfirmation.bind(this),
            downloadAsXLXS: this.downloadAsXLXS.bind(this),
            copySheetAsValues: this.copySheetAsValues.bind(this), // Register the new action
            copyMasterSheetAsValues: this.copyMasterSheetAsValues.bind(this), // Register the new action
            createFinalSheetAsValues: this.createFinalSheetAsValues.bind(this), // Register the new action


        });

                
        onWillStart(async () => {
            await loadSpreadsheetDependencies();
            await dataSources.waitForAllLoaded();
            await this.env.importData(this.spreadsheet_model);
        });
        useSetupAction({
            beforeLeave: () => this.onSpreadsheetSaved(),
        });
        dataSources.addEventListener("data-source-updated", () => {
            const sheetId = this.spreadsheet_model.getters.getActiveSheetId();
            this.spreadsheet_model.dispatch("EVALUATE_CELLS", {sheetId});
        });
    }
    closeDialog() {
        this.state.dialogDisplayed = false;
        this.state.dialogTitle = "Spreadsheet";
        this.state.dialogContent = undefined;
        this.state.dialogHideInputBox = false;
    }
    onSpreadsheetSaved() {
        const data = this.spreadsheet_model.exportData();
        this.env.saveRecord({spreadsheet_raw: data});
        this.spreadsheet_model.leaveSession();
    }
    editText(title, callback, options) {
        this.state.dialogContent = options.placeholder;
        this.state.dialogTitle = title;
        this.state.dialogDisplayed = true;
        this.confirmDialog = () => {
            callback(this.state.dialogContent);
            this.closeDialog();
        };
    }
    askConfirmation(content, confirm) {
        this.state.dialogContent = content;
        this.state.dialogDisplayed = true;
        this.state.dialogHideInputBox = true;
        this.confirmDialog = () => {
            confirm();
            this.closeDialog();
        };
    }
    async downloadAsXLXS() {
        this.ui.block();
        await waitForDataLoaded(this.spreadsheet_model);
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "action_download_spreadsheet",
            params: {
                name: this.props.record.name,
                xlsxData: this.spreadsheet_model.exportXLSX(),
            },
        });
        this.ui.unblock();
    }
    /** ----------------------------------copySheetAsValues----------------------------------------------- */
    /** Biztinct */

    
    copySheetAsValues = async function (env) {
        const spreadsheetModel = this.spreadsheet_model;
    
        if (!spreadsheetModel) {
            alert("Spreadsheet model not available.");
            return;
        }
    
        // Show the spinner
        showSpinner();
    
        try {
            // Source sheet: "TEMPLATE Employee Details"
            const sourceSheetName = "TEMPLATE Employee Details";
            const sourceSheetId = spreadsheetModel.getters.getSheetIdByName(sourceSheetName);
            if (!sourceSheetId) {
                alert('Source sheet "TEMPLATE Employee Details" not found.');
                return;
            }
    
            // Force activate the "TEMPLATE Employee Details" sheet
            const currentActiveSheetId = spreadsheetModel.getters.getActiveSheetId();
            if (currentActiveSheetId !== sourceSheetId) {
                spreadsheetModel.dispatch("ACTIVATE_SHEET", {
                    sheetIdFrom: currentActiveSheetId,
                    sheetIdTo: sourceSheetId,
                });
    
                // Wait for activation to complete before proceeding
                await new Promise((resolve) => setTimeout(resolve, 2000));
            }
    
            // Re-fetch the active sheet ID to confirm activation
            const confirmedActiveSheetId = spreadsheetModel.getters.getActiveSheetId();
            if (confirmedActiveSheetId !== sourceSheetId) {
                alert("Failed to activate the correct sheet. Stopping operation.");
                return;
            }
    
            const allSourceZones = [
                {
                    sheetId: sourceSheetId,
                    left: 0,
                    top: 0,
                    right: 0,
                    bottom: 0,
                },
            ];
    
            spreadsheetModel.selection.selectAll();
            await new Promise((resolve) => setTimeout(resolve, 4000)); // Wait to complete selection
            spreadsheetModel.dispatch("COPY", { zones: allSourceZones });
    
            const clipboardContent = spreadsheetModel.getters.getClipboardContent(allSourceZones, "onlyValue");
            if (!clipboardContent) {
                alert("Clipboard is empty. Nothing to copy.");
                return;
            }
    
            const desiredSheetName = "Employee Details";
            const existingSheetId = spreadsheetModel.getters.getSheetIdByName(desiredSheetName);
            if (existingSheetId) {
                spreadsheetModel.dispatch("DELETE_SHEET", { sheetId: existingSheetId });
            }
    
            const activeSheetId = spreadsheetModel.getters.getActiveSheetId();
            const position = spreadsheetModel.getters.getSheetIds().findIndex(
                (sheetId) => sheetId === activeSheetId
            ) + 1;
            const newSheetId = spreadsheetModel.uuidGenerator.uuidv4();
    
            spreadsheetModel.dispatch("CREATE_SHEET", { sheetId: newSheetId, position, name: desiredSheetName });
            spreadsheetModel.dispatch("ACTIVATE_SHEET", { sheetIdFrom: activeSheetId, sheetIdTo: newSheetId });
    
            const allDestinationZones = [
                {
                    sheetId: newSheetId,
                    left: 0,
                    top: 0,
                    right: 0,
                    bottom: 0,
                },
            ];
    
            spreadsheetModel.dispatch("PASTE", {
                target: allDestinationZones,
                pasteOption: "onlyValue",
            });
    


        } catch (error) {
            console.error("An error occurred:", error);
        } finally {
            // Hide the spinner after execution completes
            hideSpinner();
        }
    };
    
    


    


    
    
    //-----------------------------------copyMasterSheetAsValues--------------------------------------------



    copyMasterSheetAsValues = async function (env) {
        const spreadsheetModel = this.spreadsheet_model;
    
        if (!spreadsheetModel) {
            alert("Spreadsheet model not available.");
            return;
        }
    
        // Show the spinner
        showSpinner();
    
        try {
            const sourceSheetName = "TEMPLATE Master";
            const sourceSheetId = spreadsheetModel.getters.getSheetIdByName(sourceSheetName);
            if (!sourceSheetId) {
                alert('Source sheet "TEMPLATE Master" not found.');
                return;
            }
    
            // Force activate the "TEMPLATE Master" sheet
            const currentActiveSheetId = spreadsheetModel.getters.getActiveSheetId();
            if (currentActiveSheetId !== sourceSheetId) {
                spreadsheetModel.dispatch("ACTIVATE_SHEET", {
                    sheetIdFrom: currentActiveSheetId,
                    sheetIdTo: sourceSheetId,
                });
    
                // Wait for activation to complete before proceeding
                await new Promise((resolve) => setTimeout(resolve, 100));
            }
    
            // Re-fetch the active sheet ID to confirm activation
            const confirmedActiveSheetId = spreadsheetModel.getters.getActiveSheetId();
            if (confirmedActiveSheetId !== sourceSheetId) {
                alert("Failed to activate the correct sheet. Stopping operation.");
                return;
            }
    
            const allSourceZones = [
                {
                    sheetId: sourceSheetId,
                    left: 0,
                    top: 0,
                    right: 3,
                    bottom: 3,
                },
            ];
    
            // Explicitly call selectAll() on the activated sheet
            spreadsheetModel.selection.selectAll();
            // Delay to ensure SELECT dispatch completes
            await new Promise((resolve) => setTimeout(resolve, 100));
            spreadsheetModel.dispatch("COPY", { zones: allSourceZones });
    
            const clipboardContent = spreadsheetModel.getters.getClipboardContent(allSourceZones, "onlyValue");
            if (!clipboardContent) {
                alert("Clipboard is empty. Nothing to copy.");
                return;
            }
    
            // Ensure the sheet with the desired name exists or gets created
            const desiredSheetName = "Staging";
    
            // Check if a sheet with the name "Staging" already exists
            const existingSheetId = spreadsheetModel.getters.getSheetIdByName(desiredSheetName);
    
            if (existingSheetId) {
                // Delete the existing sheet
                spreadsheetModel.dispatch("DELETE_SHEET", { sheetId: existingSheetId });
            }
    
            // Create a new sheet with the name "Staging"
            const activeSheetId = spreadsheetModel.getters.getActiveSheetId();
            const position = spreadsheetModel.getters.getSheetIds().findIndex(
                (sheetId) => sheetId === activeSheetId
            ) + 1;
            const newSheetId = spreadsheetModel.uuidGenerator.uuidv4();
    
            spreadsheetModel.dispatch("CREATE_SHEET", { sheetId: newSheetId, position, name: desiredSheetName });
            spreadsheetModel.dispatch("ACTIVATE_SHEET", { sheetIdFrom: activeSheetId, sheetIdTo: newSheetId });
    
            // Paste content into the destination worksheet
            const allDestinationZones = [
                {
                    sheetId: newSheetId,
                    left: 0,
                    top: 0,
                    right: 0,
                    bottom: 0,
                },
            ];
    
            spreadsheetModel.dispatch("PASTE", {
                target: allDestinationZones,
            });
    
            /** Get the count of Columns and Rows of Staging sheet. */
            spreadsheetModel.selection.selectAll();
            const maxColumns = spreadsheetModel.getters.getActiveCols(); // Get the total number of columns
            const maxRows = spreadsheetModel.getters.getActiveRows(); // Get the total number of rows
    
            // Ensure the sheet with the TEMP name exists or gets created
            const desiredSheetName2 = "TEMP";
    
            // Check if a sheet with the name "TEMP" already exists
            const existingSheetId2 = spreadsheetModel.getters.getSheetIdByName(desiredSheetName2);
    
            if (existingSheetId2) {
                // Delete the existing sheet
                spreadsheetModel.dispatch("DELETE_SHEET", { sheetId: existingSheetId2 });
            }
    
            // Create a Temporary sheet with the name "TEMP"
            const activeSheetId2 = spreadsheetModel.getters.getActiveSheetId();
            const position2 = spreadsheetModel.getters.getSheetIds().findIndex(
                (sheetId) => sheetId === activeSheetId2
            ) + 1;
            const TempSheetId = spreadsheetModel.uuidGenerator.uuidv4();
    
            spreadsheetModel.dispatch("CREATE_SHEET", { sheetId: TempSheetId, position2, name: desiredSheetName2 });
            spreadsheetModel.dispatch("ACTIVATE_SHEET", { sheetIdFrom: activeSheetId2, sheetIdTo: TempSheetId });
    
            const allDestinationZones2 = [
                {
                    sheetId: TempSheetId,
                    left: 0,
                    top: 0,
                    right: 6,
                    bottom: 6,
                },
            ];
    
            spreadsheetModel.dispatch("PASTE", {
                target: allDestinationZones2,
                pasteOption: "onlyValue",
            });
    
            const lcols = maxColumns.size - 1;
            const colarray = Array.from({ length: lcols }, (_, i) => i + 1);
            spreadsheetModel.dispatch("REMOVE_COLUMNS_ROWS", {
                sheetId: TempSheetId,
                dimension: "COL",
                elements: colarray,
            });
    
            spreadsheetModel.dispatch("COPY");
            spreadsheetModel.dispatch("ACTIVATE_SHEET", { sheetIdFrom: TempSheetId, sheetIdTo: newSheetId });
            spreadsheetModel.dispatch("PASTE", {
                target: allDestinationZones,
            });
    
            const totalRows = maxRows.size;
            const rowsToDelete = [];
    
            // Find the column index for "Standard Working Hours" in the header row (row 0)
            let targetColumnIndex = -1;
    
            for (let colIndex = 0; colIndex < maxColumns.size; colIndex++) {
                const headerCell = spreadsheetModel.getters.getCell(newSheetId, colIndex, 0); // Get cell in row 0
                const headerValue = headerCell?.formattedValue || ""; // Access the formatted value or default to empty
    
                if (headerValue.trim() === "Standard Working Hours") {
                    targetColumnIndex = colIndex; // Store the index of the column
                    break; // Exit the loop once found
                }
            }
    
            for (let rowIndex = 0; rowIndex < totalRows; rowIndex++) {
                const cellObject = spreadsheetModel.getters.getCell(newSheetId, targetColumnIndex, rowIndex);
                const cellValue = cellObject.formattedValue;
    
                if (cellValue === undefined || cellValue === null || cellValue.trim() === "") {
                    rowsToDelete.push(rowIndex); // Add the row index to delete list
                }
            }
    
            rowsToDelete.reverse().forEach((rowIndex) => {
                spreadsheetModel.dispatch("REMOVE_COLUMNS_ROWS", {
                    sheetId: newSheetId,
                    dimension: "ROW",
                    elements: [rowIndex],
                });
            });
    
            // Delete TEMP sheet
            const existingSheetId3 = spreadsheetModel.getters.getSheetIdByName(desiredSheetName2);
            if (existingSheetId3) {
                spreadsheetModel.dispatch("DELETE_SHEET", { sheetId: existingSheetId3 });
            }
        } catch (error) {
            console.error("An error occurred:", error);
        } finally {
            // Hide the spinner after execution completes
            hideSpinner();
        }
    };
    


    createFinalSheetAsValues = async function (env) {
        
        const spreadsheetModel = this.spreadsheet_model;
    
        if (!spreadsheetModel) {
            alert("Spreadsheet model not available.");
            return;
        }
    
        const sourceSheetName = "Staging";
        const sourceSheetId = spreadsheetModel.getters.getSheetIdByName(sourceSheetName);
        if (!sourceSheetId) {
            alert('Source sheet "Staging" not found.');
            return;
        }
 
        // Force activate the "Staging" sheet
        const currentActiveSheetId = spreadsheetModel.getters.getActiveSheetId();
        if (currentActiveSheetId !== sourceSheetId) {
            spreadsheetModel.dispatch("ACTIVATE_SHEET", {
                sheetIdFrom: currentActiveSheetId,
                sheetIdTo: sourceSheetId,
            });
    
            // Wait for activation to complete before proceeding
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
    
        // Re-fetch the active sheet ID to confirm activation
        
        const confirmedActiveSheetId = spreadsheetModel.getters.getActiveSheetId();
        if (confirmedActiveSheetId !== sourceSheetId) {
            alert("Failed to activate the correct sheet. Stopping operation.");
            return;
        }
        
        /** The value of right and bottom doesnt matter as we are doing selectall */
        const allSourceZones = [
            {
                sheetId: sourceSheetId,
                left: 0,
                top: 0,
                right: 0,
                bottom: 0,
            },
        ];
    
          
        // Explicitly call selectAll() on the activated sheet
        spreadsheetModel.selection.selectAll();
        // Delay to ensure SELECT dispatch completes
        await new Promise((resolve) => setTimeout(resolve, 100));
        spreadsheetModel.dispatch("COPY", { zones: allSourceZones });
    
        const clipboardContent = spreadsheetModel.getters.getClipboardContent(allSourceZones, "onlyValue");
        if (!clipboardContent) {
            alert("Clipboard is empty. Nothing to copy.");
            return;
        }


        // Ensure the sheet with the desired name exists or gets created
        const desiredSheetName = "Final";

        // Check if a sheet with the name "Staging" already exists
        const existingSheetId = spreadsheetModel.getters.getSheetIdByName(desiredSheetName);

        if (existingSheetId) {
            // Delete the existing sheet
            spreadsheetModel.dispatch("DELETE_SHEET", { sheetId: existingSheetId });
        }


        // Create a new sheet with the name "Final"
        const activeSheetId = spreadsheetModel.getters.getActiveSheetId();
        const position = spreadsheetModel.getters.getSheetIds().findIndex(
            (sheetId) => sheetId === activeSheetId
        ) + 1;
        const newSheetId = spreadsheetModel.uuidGenerator.uuidv4();

        spreadsheetModel.dispatch("CREATE_SHEET", { sheetId: newSheetId, position, name: desiredSheetName });
        spreadsheetModel.dispatch("ACTIVATE_SHEET", { sheetIdFrom: activeSheetId, sheetIdTo: newSheetId });
  
    
        // Paste content into the destination worksheet
        
        const allDestinationZones = [
            {
                sheetId: newSheetId,
                left: 0,
                top: 0,
                right: 0,
                bottom: 0,
            },
        ];
        


        spreadsheetModel.dispatch("PASTE", {
            target: allDestinationZones,
            pasteOption: "onlyValue",
        });

        spreadsheetModel.selection.selectAll();
        const maxColumns = spreadsheetModel.getters.getActiveCols(); // Get the total number of columns
        const maxRows = spreadsheetModel.getters.getActiveRows(); // Get the total number of rows
        
        const allDestinationZones1 = [
            {
                sheetId: newSheetId,
                left: 0, // Starting from the first column
                top: 0,  // Starting from the first row
                right: maxColumns.size - 1, // Max column index (zero-based)
                bottom: maxRows.size - 1,  // Max row index (zero-based)
            },
        ];
        

        for (let i = 0; i < 4; i++) { // Loop to call the function 4 times
            spreadsheetModel.dispatch("SET_DECIMAL", {
                sheetId: newSheetId,
                target: allDestinationZones1,
                step: -1, // Reduce decimal places by 1 each time
            });
        }
        


        const totalRows = maxRows.size;
        const rowsToDelete = [];

        // Find the column index for "Employee Id" in the header row (row 0)
        let targetColumnIndex = -1;

        for (let colIndex = 0; colIndex < maxColumns.size; colIndex++) {
            const headerCell = spreadsheetModel.getters.getCell(newSheetId, colIndex, 0); // Get cell in row 0
            //alert("Before formatted value.");
            const headerValue = headerCell?.formattedValue || ""; // Access the formatted value or default to empty
            //alert("After formatted value.");
            if (headerValue.trim() === "Employee ID") {
                targetColumnIndex = colIndex; // Store the index of the column
                break; // Exit the loop once found
            }
        }

        for (let rowIndex = 0; rowIndex < totalRows; rowIndex++) {
            try {
                const cellObject = spreadsheetModel.getters.getCell(newSheetId, targetColumnIndex, rowIndex);
                const cellValue = cellObject.formattedValue;
        
                // Check if the cell is blank
                if (cellValue === undefined || cellValue === null || cellValue.trim() === "") {
                    rowsToDelete.push(rowIndex); // Add the row index to delete list
                }
            } catch (error) {
       
                // Fallback in case of error (e.g., cellObject is undefined)
                rowsToDelete.push(rowIndex); // Add row index to delete list as it might be blank or inaccessible
            }
        }
        

        rowsToDelete.reverse().forEach((rowIndex) => {
            spreadsheetModel.dispatch("REMOVE_COLUMNS_ROWS", {
                sheetId: newSheetId,
                dimension: "ROW",
                elements: [rowIndex],
            });
        });

        alert("Payroll calculations complete . Remember to save the Spreadsheet before importing !");

    };
    

}    

SpreadsheetRenderer.template = "spreadsheet_oca.SpreadsheetRenderer";
SpreadsheetRenderer.components = {
    Spreadsheet,
    Field,
    Dialog,
};
SpreadsheetRenderer.props = {
    record: Object,
    res_id: {type: Number, optional: true},
    model: String,
    importData: {type: Function, optional: true},
};
