# We start from the nginx alpine base image
FROM nginx:alpine

# We remove the default nginx configuration
RUN rm /etc/nginx/conf.d/default.conf

RUN mkdir -p /html
COPY index.html /html/

# Copy the configuration file into the docker image
COPY nginx.conf /etc/nginx/conf.d/