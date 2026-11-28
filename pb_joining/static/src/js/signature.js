/** @odoo-module ignore **/
(() => {
    function prepare() {
        const form = document.querySelector(".pbjp-sign");
        if (!form) return;
        const canvas=form.querySelector("canvas"), ctx=canvas.getContext("2d");
        const {agree,signer,signature}=form.elements;
        const submit=form.querySelector("[type=submit]");
        let drawing=false, ink=false;
        function ready() { submit.disabled=!(ink && agree.checked && signer.value.trim()); }
        function clear() { ctx.fillStyle="white"; ctx.fillRect(0,0,canvas.width,canvas.height); ink=false; ready(); }
        function point(event) {
            const bounds=canvas.getBoundingClientRect();
            return [(event.clientX-bounds.left)*canvas.width/bounds.width,(event.clientY-bounds.top)*canvas.height/bounds.height];
        }
        clear();
        canvas.addEventListener("pointerdown",event=>{
            if (drawing) return;
            drawing=true;canvas.setPointerCapture(event.pointerId);ctx.beginPath();ctx.moveTo(...point(event));
        });
        canvas.addEventListener("pointermove",event=>{
            if (!drawing) return;
            ctx.strokeStyle="#1e1b2e";ctx.lineWidth=3;ctx.lineCap="round";ctx.lineJoin="round";
            ctx.lineTo(...point(event));ctx.stroke();ink=true;ready();
        });
        for (const type of ["pointerup","pointercancel","lostpointercapture"]) canvas.addEventListener(type,()=>{drawing=false;});
        form.querySelector("[data-open-paper]").addEventListener("click",()=>{agree.disabled=false;});
        form.querySelector("[data-clear]").addEventListener("click",clear);
        const reuse=form.querySelector("[data-reuse]");
        if (reuse.dataset.ink) {
            reuse.hidden=false;
            reuse.addEventListener("click",()=>{
                const previous=new Image();
                previous.onload=()=>{clear();ctx.drawImage(previous,0,0,canvas.width,canvas.height);ink=true;ready();};
                previous.src=reuse.dataset.ink;
            });
        }
        agree.addEventListener("change",ready);
        signer.addEventListener("input",ready);
        form.addEventListener("submit",()=>{signature.value=canvas.toDataURL("image/png");submit.disabled=true;});
    }
    if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",prepare,{once:true});
    else prepare();
})();
