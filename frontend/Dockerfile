FROM node:20-alpine

WORKDIR /app

# Copy package files first for caching
COPY package.json package-lock.json* ./
RUN npm install

# Copy app source
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
