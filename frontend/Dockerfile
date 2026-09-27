FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package*.json ./
RUN npm install

FROM node:22-alpine AS development
WORKDIR /app
ENV NODE_ENV=development
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
