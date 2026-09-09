FROM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/incident-api ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/incident-api /incident-api
USER 65532:65532
EXPOSE 8088
ENTRYPOINT ["/incident-api"]
