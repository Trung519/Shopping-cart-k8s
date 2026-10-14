package com.shoppingcart.order.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Emit while the Java agent servlet span is active. Never log headers, query or body. */
@Component
public class RequestCompletionLoggingFilter extends OncePerRequestFilter {
    private static final Logger LOG = LoggerFactory.getLogger(RequestCompletionLoggingFilter.class);

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain chain) throws ServletException, IOException {
        long started = System.nanoTime();
        boolean completed = false;
        try {
            chain.doFilter(request, response);
            completed = true;
        } finally {
            // The console formatter reads trace_id/span_id from the agent logging event MDC.
            LOG.info("http_request_completed method={} status={} outcome={} duration_ms={}",
                    request.getMethod(), response.getStatus(), completed ? "returned" : "exception",
                    (System.nanoTime() - started) / 1_000_000);
        }
    }
}
