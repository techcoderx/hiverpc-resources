FROM nginx:alpine
RUN rm /etc/nginx/conf.d/default.conf
RUN mkdir -p /html
COPY ./frontend/curation /html/curation
COPY ./frontend/witreward /html/witreward
COPY ./frontend/nginx.conf /etc/nginx/conf.d/