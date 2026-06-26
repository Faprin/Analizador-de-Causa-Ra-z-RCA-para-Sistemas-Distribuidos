package rca.pedidos.api_pedidos.observability;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
@Slf4j
public class RequestLoggingFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain)
            throws ServletException, IOException {

        long inicio = System.currentTimeMillis();
        Exception errorCapturado = null;

        try {
            filterChain.doFilter(request, response);
        } catch (Exception e) {
            errorCapturado = e;
            throw e;
        } finally {
            long duracion = System.currentTimeMillis() - inicio;
            int status = response.getStatus();

            // Clasificación automática del tipo de evento
            String eventType = clasificarEvento(status, errorCapturado);
            String outcome   = status < 400 ? "SUCCESS" : "FAILURE";
            String severity  = status >= 500 ? "ERROR" : status >= 400 ? "WARN" : "INFO";

            // Si hay error, loguear con nivel adecuado
            if (errorCapturado != null || status >= 500) {
                log.error("event.type={} outcome={} method={} uri={} status={} duration_ms={} error.type={} error.message={}",
                        eventType, outcome,
                        request.getMethod(), request.getRequestURI(),
                        status, duracion,
                        errorCapturado != null ? errorCapturado.getClass().getSimpleName() : "NONE",
                        errorCapturado != null ? errorCapturado.getMessage() : "NONE");
            } else if (status >= 400) {
                log.warn("event.type={} outcome={} method={} uri={} status={} duration_ms={}",
                        eventType, outcome,
                        request.getMethod(), request.getRequestURI(),
                        status, duracion);
            } else {
                log.info("event.type={} outcome={} method={} uri={} status={} duration_ms={}",
                        eventType, outcome,
                        request.getMethod(), request.getRequestURI(),
                        status, duracion);
            }
        }
    }

    private String clasificarEvento(int status, Exception e) {
        if (e != null) return "UNHANDLED_ERROR";
        if (status == 401 || status == 403) return "AUTH_ERROR";
        if (status == 400 || status == 422) return "VALIDATION_ERROR";
        if (status == 404) return "NOT_FOUND";
        if (status >= 500) return "SERVER_ERROR";
        return "HTTP_REQUEST";
    }
}