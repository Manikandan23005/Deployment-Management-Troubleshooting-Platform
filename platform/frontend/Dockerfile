# --- Frontend Stage ---
FROM node:18-alpine
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Expose Vite Port
EXPOSE 3000
ENV PORT=3000

# Start Vite Development Server accessible to host
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
