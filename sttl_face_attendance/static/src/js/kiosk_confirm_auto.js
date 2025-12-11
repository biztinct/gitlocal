/** @odoo-module **/

import KioskConfirm from 'hr_attendance.kiosk_confirm';
import { patch } from "@web/core/utils/patch";
const session = require('web.session');
const MODEL_URL = '/sttl_face_attendance/static/face-api/weights/';

patch(KioskConfirm.prototype, 'face_detection_attendance_kiosk_confirm', {
    events: _.extend({}, KioskConfirm.prototype.events, {
        "click .o_hr_attendance_sign_in_out_icon": _.debounce(async function () {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert("Unable to access the camera");
            } else {
                await this.setupCamera();
            }
        }, 200, true),
    }),

    async check_employee_image(){
        try{
            const self = this;
            this.employeeDetails = await self._rpc({
                model: 'hr.employee',
                method: 'get_employee_images',
                args: [[self.employee_id]],
            });
            for (const { employee_id, image } of this.employeeDetails) {
                if(image === false) {
                    return false;
                }
            }
            return true;
        }
        catch (error) {
            console.log(error);
        }
        
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
            const overlay = this._createOverlay();
            var video;
            try {
                const video = this._createVideoElement(overlay);
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });

                video.srcObject = stream;
                video.play();

                this._bindCloseButton(video, overlay, resolve);
                this._bindAutoCapture(video, overlay, resolve);
            } catch (error) {
                alert("Unable to access the camera");
                if (video) {
                    this._stopStream(video);
                }
                overlay.remove();
                resolve(false);
            }
        });
    },

    _createOverlay() {
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.8); z-index: 1000; display: flex; align-items: center; justify-content: center;';
        document.body.appendChild(overlay);
        return overlay;
    },

    _createVideoElement(overlay) {
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

        return video;
    },

    _bindAutoCapture(video, overlay, resolve) {
            let attempts = 0;
            const self = this;

            this.autoCaptureIntervalID = setInterval(async function () {
                if (++attempts === 5) {
                    alert('Image does not exist for the employee or does not match the selected employee.');
                    if (self.autoCaptureIntervalID) {
                        window.clearInterval(self.autoCaptureIntervalID);
                        self.autoCaptureIntervalID = null;
                    }
                    if (video) {
                        self._stopStream(video);
                    }
                    if (overlay) {
                        self._destroyVideoComponents(overlay);
                    }
                    resolve(false);
                }
                const faceDetection = await faceapi.detectSingleFace(video, new faceapi.TinyFaceDetectorOptions())
                    .withFaceLandmarks()
                    .withFaceDescriptor();

                if (!faceDetection) {
                    return;
                }

                const matchingEmployeeId = await self._findMatchingEmployee(faceDetection);

                if (matchingEmployeeId && matchingEmployeeId === self.employee_id) {
                    self.employee_id = matchingEmployeeId;
                    if (self.autoCaptureIntervalID) {
                        window.clearInterval(self.autoCaptureIntervalID);
                        self.autoCaptureIntervalID = null;
                    }
                    if (video) {
                        self._stopStream(video);
                    }
                    if (overlay) {
                        self._destroyVideoComponents(overlay);
                    }

                    self._rpc({
                        model: 'hr.employee',
                        method: 'attendance_manual',
                        args: [[self.employee_id], "hr_attendance.hr_attendance_action_kiosk_mode"],
                        context: session.user_context,
                    }).then((result) => {
                        if (result.action) {
                            self.do_action(result.action);
                        } else if (result.warning) {
                            self.displayNotification({ title: result.warning, type: 'danger' });
                        }
                        resolve(true);
                    });
                }
            }, 3000);
    },

    _bindCloseButton(video, overlay, resolve) {
        try{
            const closeButton = document.getElementById('close-button');
            closeButton.addEventListener('click', () => {
                if (this.autoCaptureIntervalID) {
                    window.clearInterval(this.autoCaptureIntervalID); 
                    this.autoCaptureIntervalID = null;
                }
                if (video) {
                    this._stopStream(video);
                }
                if (overlay) {
                    this._destroyVideoComponents(overlay);
                }
                resolve(false);
            });
        }
        catch (error) {
            console.log(error);
        }
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

    _stopStream(video) {
        const stream = video.srcObject;
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            video.srcObject = null;
        }
    },

    _destroyVideoComponents(overlay) {
        const video = document.getElementById('camera-stream');
        if (video) {
            video.remove();
        }
        const closeButton = document.getElementById('close-button');
        if (closeButton) {
            closeButton.remove();
        }
        if (overlay) {
            overlay.remove();
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
