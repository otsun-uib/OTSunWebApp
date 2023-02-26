FROM amrit3701/freecad-cli:latest

WORKDIR /app
RUN pip install --upgrade pip
COPY app/requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY src/otsunwebapp otsunwebapp
COPY app/local_server.py .
CMD [ "python3.8", "local_server.py" ]
