FROM node:26-alpine

WORKDIR /app

ENV CI=true
RUN npm install -g pnpm

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

COPY . .

RUN npx tsc --noEmit
RUN pnpm build

EXPOSE 3000

CMD ["pnpm", "start"]
