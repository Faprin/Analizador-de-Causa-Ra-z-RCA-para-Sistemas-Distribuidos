package rca.autenticacion.api_autenticacion.observability;

import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

@Aspect
@Component
@Slf4j
public class ChaosLatencyAspect {

    private final ChaosController chaosController;

    public ChaosLatencyAspect(ChaosController chaosController) {
        this.chaosController = chaosController;
    }

    // Intercepta todos los métodos de todos los controllers
    @Around("execution(* rca..controllers..*(..))")
    public Object injectLatency(ProceedingJoinPoint joinPoint) throws Throwable {
        if (chaosController.isLatenciaActiva()) {
            int ms = chaosController.getLatenciaMs();
            log.warn("CHAOS: aplicando latencia de {}ms a {}", ms,
                    joinPoint.getSignature().getName());
            Thread.sleep(ms);
        }
        return joinPoint.proceed();
    }
}