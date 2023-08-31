FROM python:3.11.5

RUN mkdir -p /appfolder

COPY . /appfolder

RUN python3 -m pip install -r /appfolder/requirements.txt

WORKDIR /appfolder

EXPOSE 5000

ENTRYPOINT [ "python3" ]

CMD [ "app.py" ]