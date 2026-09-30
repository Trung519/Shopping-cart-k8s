FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod ./
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/account-service ./cmd/server
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/account-service /account-service
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/account-service"]
