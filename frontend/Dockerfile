# Changed from node:18-alpine to node:20-alpine to meet Vite's requirements
FROM node:20-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Expose the frontend port (Source: Port 5173)
EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]