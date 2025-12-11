/** @odoo-module **/

import KioskMode from 'hr_attendance.kiosk_mode';
import { patch } from "@web/core/utils/patch";
const session = require('web.session');
const MODEL_URL = '/sttl_face_attendance/static/face-api/weights/';

patch(KioskMode.prototype, 'face_detection_attendance_kiosk_mode', {
    events: _.extend({}, KioskMode.prototype.events, {
        'click .o_hr_attendance_button_face_checkin_out': function () {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert("Unable to access the camera");
                return;
            }
            this.setupCamera();
        },
    }),

    async setupCamera() {
        await Promise.all([
            faceapi.nets.tinyFaceDetector.load(MODEL_URL),
            faceapi.nets.faceLandmark68Net.load(MODEL_URL),
            faceapi.nets.faceRecognitionNet.load(MODEL_URL)
        ]);

        return new Promise(async (resolve) => {
            const overlay = this._createOverlay();
            var video;
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                const video = this._setupVideoStream(stream, overlay);
                this._bindAutoCapture(video, overlay, resolve);
                this._addEventListeners(video, overlay, resolve);
            } catch (error) {
                alert("Unable to access the camera");
                this._handleError(video, overlay, resolve);
            }
        });
    },

    _bindAutoCapture(video, overlay, resolve) {
        const self = this;
        let attempts = 0;

        this.autoCaptureIntervalID = setInterval(async () => {
            try {
                if (++attempts >= 5) {
                    alert('No matching employee found.');
                    clearInterval(self.autoCaptureIntervalID);
                    self.autoCaptureIntervalID = null;
                    self._handleError(video, overlay, resolve);
                }
                const faceDetection = await faceapi.detectSingleFace(video, new faceapi.TinyFaceDetectorOptions())
                    .withFaceLandmarks()
                    .withFaceDescriptor();

                if (!faceDetection) {
                    return;
                }

                const employeeDetails = await self._rpc({
                    model: 'hr.employee',
                    method: 'get_employee_images',
                    args: [[]],
                });

                const matchingEmployeeId = await self._findMatchingEmployee(faceDetection, employeeDetails);

                if (matchingEmployeeId) {
                    clearInterval(self.autoCaptureIntervalID);
                    self.autoCaptureIntervalID = null;
                    self._handleEmployeeDetected(matchingEmployeeId, video, overlay, resolve);
                }
            } catch (error) {
                alert('Face detection failed.');
                clearInterval(self.autoCaptureIntervalID);
                self.autoCaptureIntervalID = null;
                self._handleError(video, overlay, resolve);
            }
        }, 5000);
    },

    _createOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'camera_overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        document.body.appendChild(overlay);
        return overlay;
    },

    _setupVideoStream(stream, overlay) {
        const camDiv = document.createElement('div');
        camDiv.id = 'cam-div';
        overlay.appendChild(camDiv);

        const video = document.createElement('video');
        video.id = 'camera-stream';
        camDiv.appendChild(video);

        const closeButton = document.createElement('button');
        closeButton.id = 'close-button';
        closeButton.textContent = 'Close Camera';
        closeButton.style.marginTop = '10px';
        camDiv.appendChild(closeButton);

        video.srcObject = stream;
        video.play();

        return video;
    },

    _addEventListeners(video, overlay, resolve) {
        const self = this;

        document.getElementById('close-button').addEventListener('click', () => {
            self._handleError(video, overlay, resolve);
        });
    },

    async _findMatchingEmployee(faceDetection, employeeDetails) {
        for (const { employee_id, image } of employeeDetails) {
            if (!image) continue;

            const blob = this._base64ToBlob(image, 'image/png');
            const referenceImage = await faceapi.bufferToImage(blob);

            var referenceDescriptor;
            try {
                referenceDescriptor = await faceapi.detectSingleFace(referenceImage, new faceapi.TinyFaceDetectorOptions())
                    .withFaceLandmarks()
                    .withFaceDescriptor();
            } catch {
                continue;
            }
            if (referenceDescriptor) {
                const distance = faceapi.euclideanDistance(faceDetection.descriptor, referenceDescriptor.descriptor);
                if (distance < 0.45) return employee_id;
            }
        }
        return null;
    },

    _handleEmployeeDetected(employeeId, video, overlay, resolve) {
        this.employee_id = employeeId;
        this._stopStream(video);
        overlay.remove();

        this._rpc({
            model: 'hr.employee',
            method: 'attendance_manual',
            args: [[employeeId], 'hr_attendance.hr_attendance_action_kiosk_mode'],
            context: session.user_context,
        }).then((result) => {
            if (result.action) {
                this.do_action(result.action);
            } else if (result.warning) {
                this.displayNotification({ title: result.warning, type: 'danger' });
            }
            resolve(true);
        });
    },

    _handleError(video, overlay, resolve) {
        if (this.autoCaptureIntervalID) {
            window.clearInterval(this.autoCaptureIntervalID);
            this.autoCaptureIntervalID = null;
        }
        if (video){
            this._stopStream(video);
        }
        overlay.remove();
        resolve(false);
    },

    _stopStream(video) {
        if (video.srcObject) {
            video.srcObject.getTracks().forEach(track => track.stop());
            video.srcObject = null;
        }
    },

    _base64ToBlob(base64, mimeType) {
        const byteCharacters = atob(base64.split(',')[1] || base64);
        const byteArrays = [];

        for (let offset = 0; offset < byteCharacters.length; offset += 512) {
            const slice = byteCharacters.slice(offset, offset + 512);
            const byteArray = new Uint8Array([...slice].map(char => char.charCodeAt(0)));
            byteArrays.push(byteArray);
        }

        return new Blob(byteArrays, { type: mimeType });
    }
});
