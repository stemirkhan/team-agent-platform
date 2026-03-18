FROM node:20-alpine

WORKDIR /workspace/apps/web

COPY apps/web/package.json /workspace/apps/web/package.json
COPY apps/web/package-lock.json /workspace/apps/web/package-lock.json
RUN npm install

COPY apps/web/ /workspace/apps/web/

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
