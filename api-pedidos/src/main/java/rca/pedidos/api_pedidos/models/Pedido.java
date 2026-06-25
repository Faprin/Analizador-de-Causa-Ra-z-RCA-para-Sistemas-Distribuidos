package rca.pedidos.api_pedidos.models;

import java.time.LocalDateTime;

import org.hibernate.annotations.CreationTimestamp;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "pedidos")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Pedido {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "cliente_id", nullable = false)
    @NotNull(message = "El cliente id es requerido")
    private Long clienteId;

    @Column(name = "producto_id", nullable = false)
    @NotNull(message = "El producto id es requerido")
    private Long productoId;

    @Column(name = "cantidad", nullable = false)
    @Min(value = 1, message = "La cantidad debe ser al menos 1") // CAMBIADO a @Min
    private int cantidad;

    @Column(name = "precio_unitario", nullable = false)
    @Positive(message = "El precio unitario debe ser mayor a 0") // CAMBIADO a @Positive
    private double precioUnitario;

    @Column(name = "fecha_creacion", nullable = false)
    @CreationTimestamp
    private LocalDateTime fechaCreacion;

}
