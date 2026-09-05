FROM golang:1.23 AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/checkout .

FROM scratch
COPY --from=build /out/checkout /checkout
USER 65532:65532
ENTRYPOINT ["/checkout"]
