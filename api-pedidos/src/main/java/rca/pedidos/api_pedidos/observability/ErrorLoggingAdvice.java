package rca.pedidos.api_pedidos.observability;

import jakarta.persistence.EntityNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

@RestControllerAdvice
@Slf4j
public class ErrorLoggingAdvice {

    private static final List<String> APP_PACKAGES = List.of(
            "rca.pedidos"
    );

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<?> handleValidation(MethodArgumentNotValidException ex) {
        logStructured("VALIDATION_ERROR", ex, "WARN");
        return ResponseEntity.badRequest().body("Validation error");
    }

    @ExceptionHandler(EntityNotFoundException.class)
    public ResponseEntity<?> handleNotFound(EntityNotFoundException ex) {
        logStructured("NOT_FOUND", ex, "WARN");
        return ResponseEntity.notFound().build();
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> handleGeneric(Exception ex) {
        logStructured("UNHANDLED_ERROR", ex, "ERROR");
        return ResponseEntity.internalServerError().body("Internal error");
    }

    private void logStructured(String eventType, Exception ex, String severity) {
        MDC.put("event_type", eventType);
        MDC.put("error_type", ex.getClass().getSimpleName());
        MDC.put("error_message", ex.getMessage() != null
                ? ex.getMessage().replace("\n", " ").replace("\"", "'")
                : "null");

        MDC.put("error_origin", extractOrigin(ex));

        if (ex.getCause() != null) {
            MDC.put("error_cause_type", ex.getCause().getClass().getSimpleName());
            MDC.put("error_cause_message", ex.getCause().getMessage() != null
                    ? ex.getCause().getMessage().replace("\n", " ")
                    : "null");
        }

        if ("ERROR".equals(severity)) {
            log.error("Error capturado");
        } else {
            log.warn("Error capturado");
        }

        MDC.remove("event_type");
        MDC.remove("error_type");
        MDC.remove("error_message");
        MDC.remove("error_origin");
        MDC.remove("error_cause_type");
        MDC.remove("error_cause_message");
    }

    private String extractOrigin(Exception ex) {
        // busca en el stack trace solo las líneas de el codigo
        return Arrays.stream(ex.getStackTrace())
                .filter(frame -> APP_PACKAGES.stream()
                        .anyMatch(pkg -> frame.getClassName().startsWith(pkg)))
                .map(frame -> frame.getClassName()
                        .substring(frame.getClassName().lastIndexOf('.') + 1)
                        + "." + frame.getMethodName()
                        + "(" + frame.getFileName()
                        + ":" + frame.getLineNumber() + ")")
                .limit(3)
                .collect(Collectors.joining(" -> "));
    }
}