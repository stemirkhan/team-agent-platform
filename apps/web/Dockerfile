FROM node:20-alpine

WORKDIR /workspace/apps/web

COPY apps/web/package.json /workspace/apps/web/package.json
RUN npm install

COPY apps/web/ /workspace/apps/web/

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
