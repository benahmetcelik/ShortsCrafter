FROM ubuntu:22.04

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

RUN apt-get update && apt-get install -y python3-pip ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY auto_video/ /app/auto_video/
COPY run.py main.py generator.py ./
COPY data/ /app/data/

CMD ["python3", "run.py", "all"]
