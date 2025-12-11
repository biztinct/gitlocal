/** @odoo-module **/

import MyAttendances from 'hr_attendance.my_attendances';
import { patch } from "@web/core/utils/patch";
const session = require('web.session');
const MODEL_URL = '/sttl_face_attendance/static/face-api/weights/';


patch(MyAttendances.prototype, 'face_detection_attendance', {

    async update_attendance() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert("Unable to access the camera");
            return;
        }
        await this.setupCamera();
    },

    async check_employee_image(){
        const self = this;
        this.employeeDetails = await self._rpc({
            model: 'hr.employee',
            method: 'get_employee_images',
            args: [[self.employee.id]],
        });
        for (const { employee_id, image } of this.employeeDetails) {
            if(image === false) {
                return false;
            }
        }
        return true;
    },

    async setupCamera() {
        const image_exist = await this.check_employee_image();
        if(!image_exist){
            alert('Image does not exist for the employee');
            return;
        }
        await Promise.all([
            faceapi.nets.tinyFaceDetector.load(MODEL_URL),
            faceapi.nets.faceLandmark68Net.load(MODEL_URL),
            faceapi.nets.faceRecognitionNet.load(MODEL_URL)
        ]);

        return new Promise(async (resolve) => {
            const self = this;
            const overlay = this._createOverlay();
            var video;
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                video = document.createElement('video');
                video.id = 'camera-stream';
                video.srcObject = stream;
                video.play();
                overlay.querySelector('#cam-div').appendChild(video);

                const closeButton = self._createButton('Close Camera', 'close-button');
                self._bindAutoCapture(video, overlay, resolve);

                overlay.querySelector('#cam-div').appendChild(closeButton);

                closeButton.addEventListener('click', () => {
                    self._cleanupCamera(video, overlay, resolve, false);
                });
            } catch (error) {
                alert("Unable to access the camera");
                self._cleanupCamera(video, overlay, resolve, false);
            }
        });
    },

    _bindAutoCapture(video, overlay, resolve) {
        let attempts = 0;
        const self = this;
        this.autoCaptureIntervalID =  setInterval(async function() {
            if(++attempts == 5){
                alert('Face does not match with the selected employee.');
                resolve(false);
                self._cleanupCamera(video, overlay, resolve, false);
                self.autoCaptureIntervalID = null;
                window.clearInterval(self.autoCaptureIntervalID);
            }
            const faceDetection = await faceapi.detectSingleFace(video, new faceapi.TinyFaceDetectorOptions())
                .withFaceLandmarks()
                .withFaceDescriptor();

            if (!faceDetection) {
                return;
            }

            const matchingEmployeeId = await self._findMatchingEmployee(faceDetection);

            if (matchingEmployeeId && matchingEmployeeId === self.employee.id) {
                window.clearInterval(self.autoCaptureIntervalID);
                self.autoCaptureIntervalID = null;
                self._handleEmployeeDetected(matchingEmployeeId, video, overlay, resolve);
            }
        }, 3000);
    },

    _createOverlay() {
        const overlay = document.createElement('div');
        overlay.style.position = 'fixed';
        overlay.id = 'camera_overlay';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        overlay.style.zIndex = '1000';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        document.body.appendChild(overlay);

        const cam_div = document.createElement('div');
        cam_div.id = 'cam-div';
        overlay.appendChild(cam_div);

        return overlay;
    },

    _createButton(text, id) {
        const button = document.createElement('button');
        button.id = id;
        button.textContent = text;
        button.style.marginTop = '10px';
        return button;
    },

    async _findMatchingEmployee(faceDetection) {
        for (const { employee_id, image } of this.employeeDetails) {
            const blob = this._base64ToBlob(image, 'image/png');
            const referenceImage = await faceapi.bufferToImage(blob);
            var referenceDescriptor;
            try {
                referenceDescriptor = await faceapi.detectSingleFace(referenceImage, new faceapi.TinyFaceDetectorOptions())
                    .withFaceLandmarks()
                    .withFaceDescriptor();
            } catch (error) {
                continue;
            }
            if (referenceDescriptor) {
                const distance = faceapi.euclideanDistance(faceDetection.descriptor, referenceDescriptor.descriptor);
                if (distance < 0.45) {
                    return employee_id;
                }
            }
        }
        return null;
    },

    async _handleEmployeeDetected(employeeId, video, overlay, resolve) {
        this.employee_id = employeeId;
        this._rpc({
            model: 'hr.employee',
            method: 'attendance_manual',
            args: [[this.employee.id], 'hr_attendance.hr_attendance_action_my_attendances'],
            context: session.user_context,
        }).then((result) => {
            if (result.action) {
                this.do_action(result.action);
            } else if (result.warning) {
                this.displayNotification({ title: result.warning, type: 'danger' });
            }
            resolve(true);
        });
        this._cleanupCamera(video, overlay, resolve, true);
    },

    _cleanupCamera(video, overlay, resolve, success) {
        if (this.autoCaptureIntervalID) {
            window.clearInterval(this.autoCaptureIntervalID);
            this.autoCaptureIntervalID = null;
        }
        if(video){
            this._stopStream(video);
        }
        if(overlay){
            overlay.remove();
        }
        resolve(success);
    },

    _stopStream(video) {
        const stream = video.srcObject;
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            video.srcObject = null;
        }
    },

    _base64ToBlob(base64, mimeType) {
        const parts = base64.split(',');
        if (parts.length === 2) {
            base64 = parts[1];  
        }
        base64 = base64.replace(/=+$/, '');
        const byteCharacters = atob(base64);
        const byteArrays = [];
    
        for (let offset = 0; offset < byteCharacters.length; offset += 512) {
            const slice = byteCharacters.slice(offset, offset + 512);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }
    
        return new Blob(byteArrays, { type: mimeType });
    }
    
});
