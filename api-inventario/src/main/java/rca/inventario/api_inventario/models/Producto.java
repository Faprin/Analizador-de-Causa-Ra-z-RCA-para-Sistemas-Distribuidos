package rca.inventario.api_inventario.models;

import java.time.LocalDateTime;

import org.hibernate.annotations.CurrentTimestamp;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "Producto")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Producto {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long productId;

    @Column(name = "nombre_producto")
    @NotBlank(message = "El nombre del producto no puede estar en blanco")
    private String nombreProducto;

    @Column(name = "precio")
    @NotNull(message = "El precio no puede estar vacio")
    private double precio;
    
    @Column(name = "stock")
    @NotNull(message = "El stock no puede estar vacio")
    private int stock;
    
    @CurrentTimestamp
    private LocalDateTime fechaCreacion;
}