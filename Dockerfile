FROM binwiederhier/ntfy
RUN apk add py3-pip py3-flask py3-waitress
RUN mkdir /app
WORKDIR /app
COPY ./server.py ./app.py /app/
ENTRYPOINT ["waitress-serve"] 
CMD ["--host", "0.0.0.0", "--port", "5000", "--call", "app:createApp"]
