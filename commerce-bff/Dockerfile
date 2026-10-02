FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN GOMEMLIMIT=128MiB GOMAXPROCS=2 CGO_ENABLED=0 GOOS=linux go build -p 2 -trimpath -ldflags="-s -w" -o /out/commerce-bff ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/commerce-bff /commerce-bff
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/commerce-bff"]
