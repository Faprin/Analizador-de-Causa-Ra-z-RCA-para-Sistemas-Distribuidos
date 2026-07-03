package rca.inventario.api_inventario.observability;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
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

            String eventType = clasificarEvento(status, errorCapturado);
            String outcome = status < 400 ? "SUCCESS" : "FAILURE";

            MDC.put("event_type", eventType);
            MDC.put("outcome", outcome);
            MDC.put("http_method", request.getMethod());
            MDC.put("http_uri", request.getRequestURI());
            MDC.put("http_status", String.valueOf(status));
            MDC.put("duration_ms", String.valueOf(duracion));

            if (errorCapturado != null) {
                MDC.put("error_type", errorCapturado.getClass().getSimpleName());
                MDC.put("error_message", errorCapturado.getMessage() != null ? errorCapturado.getMessage() : "null");
            }

            if (errorCapturado != null || status >= 500) {
                log.error("Peticion completada");
            } else if (status >= 400) {
                log.warn("Peticion completada");
            } else {
                log.info("Peticion completada");
            }

            // despues del logeo limpio
            MDC.remove("event_type");
            MDC.remove("outcome");
            MDC.remove("http_method");
            MDC.remove("http_uri");
            MDC.remove("http_status");
            MDC.remove("duration_ms");
            MDC.remove("error_type");
            MDC.remove("error_message");
        }
    }

    private String clasificarEvento(int status, Exception e) {
        if (e != null)                      return "UNHANDLED_ERROR";
        if (status == 401 || status == 403) return "AUTH_ERROR";
        if (status == 400 || status == 422) return "VALIDATION_ERROR";
        if (status == 404)                  return "NOT_FOUND";
        if (status >= 500)                  return "SERVER_ERROR";
        return "HTTP_REQUEST";
    }
}