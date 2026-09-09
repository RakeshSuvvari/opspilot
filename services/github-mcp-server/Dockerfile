FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/github-mcp-server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/github-mcp-server /github-mcp-server
COPY --from=build /src/fixtures/demo.json /fixtures/demo.json
ENV OPSPILOT_GITHUB_FIXTURE_FILE=/fixtures/demo.json
EXPOSE 8090
USER 65532:65532
ENTRYPOINT ["/github-mcp-server"]
