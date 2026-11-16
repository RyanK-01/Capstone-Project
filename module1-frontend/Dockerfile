FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Build the application without mock data
RUN npm run build

# Expose port
EXPOSE 3000

# Run the application WITH mock data
#CMD ["npm", "run", "dev"]

# Run the application without mock data
CMD ["npm", "start"]