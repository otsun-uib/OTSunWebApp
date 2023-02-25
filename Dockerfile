FROM amrit3701/freecad-cli:latest

WORKDIR /app
RUN pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY src/otsunwebapp otsunwebapp
COPY local_server.py .
CMD [ "python3.8", "local_server.py" ]
