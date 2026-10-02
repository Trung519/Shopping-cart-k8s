FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod ./
COPY . .
RUN GOMEMLIMIT=128MiB GOMAXPROCS=2 CGO_ENABLED=0 GOOS=linux go build -p 2 -trimpath -ldflags="-s -w" -o /out/account-service ./cmd/server
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/account-service /account-service
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/account-service"]
