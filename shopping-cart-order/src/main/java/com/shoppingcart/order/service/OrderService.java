package com.shoppingcart.order.service;

import com.shoppingcart.order.dto.CreateOrderRequest;
import com.shoppingcart.order.dto.UpdateOrderStatusRequest;
import com.shoppingcart.order.entity.Order;
import com.shoppingcart.order.entity.OrderItem;
import com.shoppingcart.order.entity.OrderStatus;
import com.shoppingcart.order.entity.ShippingAddress;
import com.shoppingcart.order.repository.OrderRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.EnumSet;
import java.util.List;
import java.util.UUID;

/**
 * Service for managing orders.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final OrderEventPublisher eventPublisher;

    /**
     * Creates a new order.
     */
    @Transactional
    public Order createOrder(CreateOrderRequest request) {
        Order order = new Order();
        order.setCustomerId(request.customerId());
        order.setStatus(OrderStatus.PENDING);
        order.setCurrency(request.currency() != null ? request.currency().trim().toUpperCase() : "VND");

        // Add items
        BigDecimal totalAmount = BigDecimal.ZERO;
        for (var itemRequest : request.items()) {
            OrderItem item = new OrderItem();
            item.setProductId(itemRequest.productId());
            item.setProductName(itemRequest.productName());
            item.setQuantity(itemRequest.quantity());
            item.setUnitPrice(itemRequest.unitPrice());
            order.addItem(item);
            totalAmount = totalAmount.add(item.getSubtotal());
        }
        order.setTotalAmount(totalAmount);

        // Set shipping address
        if (request.shippingAddress() != null) {
            order.setShippingAddress(new ShippingAddress(
                request.shippingAddress().street(),
                request.shippingAddress().city(),
                request.shippingAddress().state(),
                request.shippingAddress().postalCode(),
                request.shippingAddress().country()
            ));
        }

        Order savedOrder = orderRepository.save(order);
        log.info("Created order: orderId={}, customerId={}, total={}",
            savedOrder.getId(), savedOrder.getCustomerId(), savedOrder.getTotalAmount());

        safelyPublishEvent(
            () -> eventPublisher.publishOrderCreated(savedOrder, null),
            "order.created",
            savedOrder.getId()
        );

        return savedOrder;
    }

    /**
     * Gets an order by ID.
     */
    @Transactional(readOnly = true)
    public Order getOrder(UUID orderId) {
        return orderRepository.findById(orderId)
            .orElseThrow(() -> new OrderNotFoundException(orderId));
    }

    /**
     * Lists orders for a customer.
     */
    @Transactional(readOnly = true)
    public List<Order> getOrdersByCustomer(String customerId) {
        return orderRepository.findByCustomerId(customerId);
    }

    /**
     * Lists orders for marketplace operators.
     */
    @Transactional(readOnly = true)
    public List<Order> getOrdersForOperations(OrderStatus status) {
        return status == null ? orderRepository.findAll() : orderRepository.findByStatus(status);
    }

    /**
     * Updates order status and publishes appropriate event.
     */
    @Transactional
    public Order updateOrderStatus(UUID orderId, UpdateOrderStatusRequest request, String correlationId) {
        Order order = getOrder(orderId);
        OrderStatus previousStatus = order.getStatus();
        OrderStatus newStatus = request.status();

        validateStatusTransition(previousStatus, newStatus);
        validateOperationalDetails(newStatus, request);

        order.setStatus(newStatus);

        switch (newStatus) {
            case PAID -> {
                order.setPaidAt(Instant.now());
                orderRepository.save(order);
                safelyPublishEvent(
                    () -> eventPublisher.publishOrderPaid(order, request.paymentId(), request.paymentMethod(), correlationId),
                    "order.paid",
                    order.getId()
                );
            }
            case SHIPPED -> {
                order.setShippedAt(Instant.now());
                order.setTrackingNumber(request.trackingNumber());
                order.setCarrier(request.carrier());
                orderRepository.save(order);
                LocalDate estimatedDelivery = request.estimatedDelivery() != null
                    ? request.estimatedDelivery()
                    : LocalDate.now().plusDays(5);
                safelyPublishEvent(
                    () -> eventPublisher.publishOrderShipped(order, estimatedDelivery, correlationId),
                    "order.shipped",
                    order.getId()
                );
            }
            case COMPLETED -> {
                order.setCompletedAt(Instant.now());
                orderRepository.save(order);
                safelyPublishEvent(
                    () -> eventPublisher.publishOrderCompleted(order, correlationId),
                    "order.completed",
                    order.getId()
                );
            }
            default -> orderRepository.save(order);
        }

        log.info("Updated order status: orderId={}, from={}, to={}",
            orderId, previousStatus, newStatus);

        return order;
    }

    /**
     * Cancels an order.
     */
    @Transactional
    public Order cancelOrder(UUID orderId, String reason, String cancelledBy, String correlationId) {
        Order order = getOrder(orderId);

        if (order.getStatus() != OrderStatus.PENDING
                && order.getStatus() != OrderStatus.PAID
                && order.getStatus() != OrderStatus.CONFIRMED
                && order.getStatus() != OrderStatus.PROCESSING) {
            throw new IllegalStateException("Cannot cancel order in status: " + order.getStatus());
        }

        order.setStatus(OrderStatus.CANCELLED);
        order.setCancelledAt(Instant.now());
        order.setCancellationReason(reason);

        Order savedOrder = orderRepository.save(order);

        log.info("Cancelled order: orderId={}, reason={}", orderId, reason);

        safelyPublishEvent(
            () -> eventPublisher.publishOrderCancelled(savedOrder, cancelledBy, correlationId),
            "order.cancelled",
            savedOrder.getId()
        );

        return savedOrder;
    }

    private void safelyPublishEvent(Runnable publishAction, String eventType, UUID orderId) {
        try {
            publishAction.run();
        } catch (RuntimeException ex) {
            log.warn("Failed to publish event: eventType={}, orderId={}", eventType, orderId, ex);
        }
    }

    private void validateStatusTransition(OrderStatus from, OrderStatus to) {
        boolean valid = permittedNextStatuses(from).contains(to);

        if (!valid) {
            throw new IllegalStateException(
                String.format("Invalid status transition from %s to %s", from, to));
        }
    }

    private EnumSet<OrderStatus> permittedNextStatuses(OrderStatus status) {
        return switch (status) {
            case PENDING -> EnumSet.of(OrderStatus.PAID, OrderStatus.CONFIRMED, OrderStatus.CANCELLED);
            case PAID -> EnumSet.of(OrderStatus.CONFIRMED, OrderStatus.CANCELLED);
            case CONFIRMED -> EnumSet.of(OrderStatus.PROCESSING, OrderStatus.CANCELLED);
            case PROCESSING -> EnumSet.of(OrderStatus.SHIPPED, OrderStatus.CANCELLED);
            case SHIPPED -> EnumSet.of(OrderStatus.DELIVERED);
            case DELIVERED -> EnumSet.of(OrderStatus.COMPLETED);
            case COMPLETED, CANCELLED -> EnumSet.noneOf(OrderStatus.class);
        };
    }

    private void validateOperationalDetails(OrderStatus status, UpdateOrderStatusRequest request) {
        if (status == OrderStatus.PAID && (request.paymentId() == null || request.paymentId().isBlank())) {
            throw new IllegalStateException("A payment ID is required when marking an order as paid");
        }
        if (status == OrderStatus.SHIPPED) {
            if (request.trackingNumber() == null || request.trackingNumber().isBlank()) {
                throw new IllegalStateException("A tracking number is required when shipping an order");
            }
            if (request.carrier() == null || request.carrier().isBlank()) {
                throw new IllegalStateException("A carrier is required when shipping an order");
            }
        }
    }

    /**
     * Exception thrown when order is not found.
     */
    public static class OrderNotFoundException extends RuntimeException {
        public OrderNotFoundException(UUID orderId) {
            super("Order not found: " + orderId);
        }
    }
}
