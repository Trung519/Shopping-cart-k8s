package com.shoppingcart.order.controller;

import com.shoppingcart.order.dto.*;
import com.shoppingcart.order.entity.Order;
import com.shoppingcart.order.entity.OrderStatus;
import com.shoppingcart.order.service.OrderService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;

    @PostMapping
    public ResponseEntity<OrderResponse> createOrder(
            @Valid @RequestBody CreateOrderRequest request,
            @RequestHeader(value = "X-User-ID", required = false) String userId,
            @RequestHeader(value = "X-User-Roles", required = false) String roles) {
        requireOwnerOrOperator(request.customerId(), userId, roles);
        Order order = orderService.createOrder(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(OrderResponse.from(order));
    }

    @GetMapping("/{orderId}")
    public ResponseEntity<OrderResponse> getOrder(
            @PathVariable UUID orderId,
            @RequestHeader(value = "X-User-ID", required = false) String userId,
            @RequestHeader(value = "X-User-Roles", required = false) String roles) {
        Order order = orderService.getOrder(orderId);
        requireOwnerOrOperator(order.getCustomerId(), userId, roles);
        return ResponseEntity.ok(OrderResponse.from(order));
    }

    @GetMapping
    public ResponseEntity<List<OrderResponse>> getOrdersByCustomer(
            @RequestParam String customerId,
            @RequestHeader(value = "X-User-ID", required = false) String userId,
            @RequestHeader(value = "X-User-Roles", required = false) String roles) {
        requireOwnerOrOperator(customerId, userId, roles);
        List<Order> orders = orderService.getOrdersByCustomer(customerId);
        return ResponseEntity.ok(orders.stream().map(OrderResponse::from).toList());
    }

    @GetMapping("/admin")
    public ResponseEntity<List<OrderResponse>> getOrdersForOperations(
            @RequestParam(required = false) OrderStatus status,
            @RequestHeader(value = "X-User-Roles", required = false) String roles) {
        requireOperator(roles);
        List<Order> orders = orderService.getOrdersForOperations(status);
        return ResponseEntity.ok(orders.stream().map(OrderResponse::from).toList());
    }

    @PatchMapping("/{orderId}/status")
    public ResponseEntity<OrderResponse> updateOrderStatus(
            @PathVariable UUID orderId,
            @Valid @RequestBody UpdateOrderStatusRequest request,
            @RequestHeader(value = "X-Correlation-ID", required = false) String correlationId,
            @RequestHeader(value = "X-User-Roles", required = false) String roles) {
        requireOperator(roles);
        Order order = orderService.updateOrderStatus(orderId, request, correlationId);
        return ResponseEntity.ok(OrderResponse.from(order));
    }

    @PostMapping("/{orderId}/cancel")
    public ResponseEntity<OrderResponse> cancelOrder(
            @PathVariable UUID orderId,
            @Valid @RequestBody CancelOrderRequest request,
            @RequestHeader(value = "X-Correlation-ID", required = false) String correlationId,
            @RequestHeader(value = "X-User-ID", required = false) String userId,
            @RequestHeader(value = "X-User-Roles", required = false) String roles) {
        Order existingOrder = orderService.getOrder(orderId);
        requireOwnerOrOperator(existingOrder.getCustomerId(), userId, roles);
        Order order = orderService.cancelOrder(orderId, request.reason(), userId, correlationId);
        return ResponseEntity.ok(OrderResponse.from(order));
    }

    @ExceptionHandler(OrderService.OrderNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(OrderService.OrderNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse("NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ErrorResponse> handleIllegalState(IllegalStateException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
            .body(new ErrorResponse("INVALID_STATE", ex.getMessage()));
    }

    public record ErrorResponse(String code, String message) {}

    private void requireOwnerOrOperator(String customerId, String userId, String roles) {
        if ((userId == null || !userId.equals(customerId)) && !isOperator(roles)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Order access denied");
        }
    }

    private void requireOperator(String roles) {
        if (!isOperator(roles)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Order operator role required");
        }
    }

    private boolean isOperator(String roles) {
        if (roles == null) {
            return false;
        }
        for (String role : roles.toLowerCase().split(",")) {
            String normalized = role.trim();
            if (normalized.equals("platform-admin")
                    || normalized.equals("order-operator")
                    || normalized.equals("finance-operator")) {
                return true;
            }
        }
        return false;
    }
}
