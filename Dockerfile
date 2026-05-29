# Use a lightweight Nginx alpine image to serve the static frontend
FROM nginx:alpine

# Add a label for identification
LABEL maintainer="djw"

# Copy static assets to the default Nginx web root directory
COPY index.html styles.css app.js data.json geocache.json /usr/share/nginx/html/

# Expose port 80 for web traffic
EXPOSE 8080

# Start Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]
