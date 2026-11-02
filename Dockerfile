# Use a lightweight Nginx alpine image to serve the static frontend
FROM nginx:alpine

# Add a label for identification
LABEL maintainer="djw"

# Ensure latest system CA certificates (fixes eMudhra/emSign CA security incident)
RUN apk update && apk upgrade --no-cache ca-certificates && update-ca-certificates

# Copy static assets to the default Nginx web root directory
COPY index.html styles.css app.js data.json geocache.json /usr/share/nginx/html/

# Expose port 80 for web traffic
EXPOSE 80

# Start Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]
