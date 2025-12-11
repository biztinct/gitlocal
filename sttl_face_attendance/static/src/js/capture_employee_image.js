odoo.define('face_attendance.capture_image', function (require) {
    "use strict";

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var QWeb = core.qweb;
    const session = require('web.session');

    var CaptureEmployeeImage = AbstractAction.extend({
        init: function (parent, action) {
            this.employee_id = action.params.employee_id;
            this._super.apply(this, arguments);
        },

        start: function () {
            try{
                this._super.apply(this, arguments);
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    alert("Unable to access the camera");
                    this.trigger_up('history_back');
                } else {
                    this.$el.html(QWeb.render("CaptureEmployeeImage", {}));
                    this._start_video_stream();
                    this._bind_events();
                }
            }
            catch (error) {
                console.log(error);
            }
            
        },

        _start_video_stream: function () {
            const self = this;
            setTimeout(() => {
                navigator.mediaDevices.getUserMedia({ video: true })
                    .then(function (stream) {
                        var video = document.getElementById('video');
                        video.srcObject = stream;
                    })
                    .catch(function (err) {
                        self._stop_stream();
                        alert("Unable to access the camera");
                        self.trigger_up('history_back');
                    });
            }, 500);
        },

        _bind_events: function () {
            this.$('#btn-close').on('click', this._on_close.bind(this));
            this.$('#btn-click').on('click', this._on_capture.bind(this));
        },

        _on_capture: function () {
            try {
                const self = this;

                var video = document.getElementById('video');
                var canvas = document.getElementById('canvas');
                var context = canvas.getContext('2d');

                const targetWidth = 320;
                const targetHeight = 240;

                canvas.width = targetWidth;
                canvas.height = targetHeight;

                context.drawImage(video, 0, 0, targetWidth, targetHeight);

                var imageData = canvas.toDataURL('image/png');

                this._rpc({
                    model: 'hr.employee',
                    method: 'register_face',
                    args: [[this.employee_id], imageData],
                    context: session.user_context,
                })
                .then(function (result) {
                    self._on_close();
                });
            } catch {
                this._on_close();
            }
        },

        _stop_stream: function () {
            var video = document.getElementById('video');
            if (video.srcObject) {
                let tracks = video.srcObject.getTracks();
                tracks.forEach(track => track.stop());
                video.srcObject = null;
            }
        },

        _on_close: function () {
            this._stop_stream();
            this.$('.o_capture_image_modal').remove();
            this.trigger_up('history_back');
        }
    });

    core.action_registry.add('new_employee_image', CaptureEmployeeImage);

    return CaptureEmployeeImage;
});
