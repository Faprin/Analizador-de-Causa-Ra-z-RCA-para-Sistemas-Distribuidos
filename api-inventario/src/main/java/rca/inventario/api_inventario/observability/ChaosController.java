package rca.inventario.api_inventario.observability;

import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/chaos")
@Slf4j
public class ChaosController {

    private final DataSource dataSource;
    private final List<Connection> connectionesRetenidas = new ArrayList<>();
    private volatile boolean latenciaActiva = false;
    private volatile int latenciaMs = 0;

    public ChaosController(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    // fall que satura el pool de conexiones de PostgreSQL
    @PostMapping("/db-saturate")
    public ResponseEntity<?> saturaDB(@RequestParam(defaultValue = "30") int segundos)
            throws SQLException, InterruptedException {

        log.warn("CHAOS: saturando pool de conexiones durante {}s", segundos);

        // Roba todas las conexiones del pool (por defecto HikariCP tiene 10)
        for (int i = 0; i < 10; i++) {
            try {
                connectionesRetenidas.add(dataSource.getConnection());
            } catch (SQLException e) {
                log.warn("CHAOS: pool agotado en conexion {}", i);
                break;
            }
        }

        Thread.sleep(segundos * 1000L);

        for (Connection conn : connectionesRetenidas) {
            conn.close();
        }
        connectionesRetenidas.clear();

        log.warn("CHAOS: pool de conexiones liberado");
        return ResponseEntity.ok("Pool saturado durante " + segundos + "s");
    }

    // fallo de latencia en el AOP ====== NO DISPONIBLE
    @PostMapping("/latency/start")
    public ResponseEntity<?> iniciarLatencia(@RequestParam int ms) {
        this.latenciaMs = ms;
        this.latenciaActiva = true;
        log.warn("CHAOS: latencia global activada {}ms por peticion", ms);
        return ResponseEntity.ok("Latencia activada: " + ms + "ms");
    }

    // ====== NO DISPONIBLE
    @PostMapping("/latency/stop")
    public ResponseEntity<?> detenerLatencia() {
        this.latenciaActiva = false;
        this.latenciaMs = 0;
        log.warn("CHAOS: latencia global desactivada");
        return ResponseEntity.ok("Latencia desactivada");
    }

    @PostMapping("/error")
    public ResponseEntity<?> error(@RequestParam String type) {
        log.warn("CHAOS: inyectando error de tipo {}", type);
        switch (type) {
            case "npe"     -> throw new NullPointerException("CHAOS: null pointer simulado");
            case "db"      -> throw new RuntimeException("CHAOS: conexion a base de datos perdida");
            case "timeout" -> throw new RuntimeException("CHAOS: timeout en servicio externo");
            default        -> throw new IllegalArgumentException("Tipo desconocido: " + type);
        }
    }

    public boolean isLatenciaActiva() { return latenciaActiva; }
    public int getLatenciaMs() { return latenciaMs; }
}