package rca.pedidos.api_pedidos.models.payload;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Getter
public class ProductoResponse {
    private Long productId;
    private String nombreProducto;
    private double precio;
    private int stock;
}
