FROM golang:1.23-alpine AS builder

WORKDIR /app
COPY . .
RUN go mod tidy && go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o billing-service .

FROM alpine:3.20
RUN apk --no-cache add ca-certificates
WORKDIR /app
COPY --from=builder /app/billing-service .

EXPOSE 8020
CMD ["./billing-service"]
