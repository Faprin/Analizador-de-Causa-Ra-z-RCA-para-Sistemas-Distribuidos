package rca.inventario.api_inventario.observability;

import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/chaos")
@Profile("!prod")
@Slf4j
public class ChaosController {

    @PostMapping("/latency")
    public ResponseEntity<?> latency(@RequestParam int ms) throws InterruptedException {
        log.warn("CHAOS: Insertando latencia de {}ms", ms);
        Thread.sleep(ms);
        return ResponseEntity.ok("Latencia inyectada " + ms + "ms");
    }

    @PostMapping("/error")
    public ResponseEntity error(@RequestParam String tipo) {
        log.warn("CHAOS: Insertando error del tipo {}", tipo);

        switch (tipo) {
            case "npe" -> throw new NullPointerException("CHAOS: null pointer simulado");
            case "db" -> throw new RuntimeException("CHAOS: conexion a base de datos perdida simulada");
            case "timeout" -> throw new NullPointerException("CHAOS: timeout en servicio externo");
            default -> throw new IllegalArgumentException("Tipo de caos desconocido: " + tipo);
        }
    }

    @PostMapping("/unaviable")
    public ResponseEntity<?> servicioNoDisponible() {
        log.error("CHAOS: servicio marcado como no disponible");
        return ResponseEntity.status(503).body("Service temporarily unavailable");
    }
}
