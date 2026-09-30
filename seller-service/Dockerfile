FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/seller-service ./cmd/server
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/seller-service /seller-service
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/seller-service"]
