FROM golang:1.27-alpine AS build
WORKDIR /src

COPY go.mod ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/k8s-mcp-server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/k8s-mcp-server /k8s-mcp-server
EXPOSE 8080
USER 65532:65532
ENTRYPOINT ["/k8s-mcp-server"]
