FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/inventory .

FROM scratch
COPY --from=build /out/inventory /inventory
USER 65532:65532
ENTRYPOINT ["/inventory"]
