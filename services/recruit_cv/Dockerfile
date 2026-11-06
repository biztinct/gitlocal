FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models OMP_NUM_THREADS=2 RECRUIT_CV_THREADS=2 RECRUIT_CV_OCR=tesseract
WORKDIR /service
COPY requirements.txt requirements-linux.lock ./
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libgomp1 tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie tesseract-ocr-ind && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-linux.lock
COPY app.py employment.py .
RUN useradd --uid 10001 --create-home cv && mkdir /models && chown cv /models
USER cv
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
