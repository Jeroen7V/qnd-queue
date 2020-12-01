FROM python:2.7-alpine

EXPOSE 8888
RUN mkdir /database
VOLUME /database

WORKDIR /src
COPY ./qnd /src

RUN pip install --no-cache-dir -r /src/requirements.txt

CMD ["python", "qndbmq.py"]
