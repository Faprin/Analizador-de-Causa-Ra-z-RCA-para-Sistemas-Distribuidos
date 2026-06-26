package rca.inventario.api_inventario.observability;

import jakarta.persistence.EntityNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
@Slf4j
public class ErrorLoggingAdvice {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<?> handleValidation(MethodArgumentNotValidException ex) {
        log.warn("event.type=VALIDATION_ERROR error.type={} error.message={}",
                ex.getClass().getSimpleName(),
                ex.getBindingResult().getAllErrors().get(0).getDefaultMessage());
        return ResponseEntity.badRequest().body("Validation error");
    }

    @ExceptionHandler(EntityNotFoundException.class)
    public ResponseEntity<?> handleNotFound(EntityNotFoundException ex) {
        log.warn("event.type=NOT_FOUND error.type={} error.message={}",
                ex.getClass().getSimpleName(), ex.getMessage());
        return ResponseEntity.notFound().build();
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> handleGeneric(Exception ex) {
        log.error("event.type=UNHANDLED_ERROR error.type={} error.message={}",
                ex.getClass().getSimpleName(), ex.getMessage(), ex);
        return ResponseEntity.internalServerError().body("Internal error");
    }
}