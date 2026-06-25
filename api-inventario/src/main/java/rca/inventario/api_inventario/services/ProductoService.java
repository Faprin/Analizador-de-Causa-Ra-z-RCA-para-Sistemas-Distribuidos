package rca.inventario.api_inventario.services;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import lombok.RequiredArgsConstructor;
import rca.inventario.api_inventario.models.Producto;
import rca.inventario.api_inventario.repository.ProductoRepository;

@Service
@RequiredArgsConstructor
public class ProductoService {

    private final ProductoRepository ProductoRepository;

    public List<Producto> obtenerTodosLosProductos() {
        return ProductoRepository.findAll();
    }

    public Producto obtenerProductoPorId(Long id) {
        // Utilizamos orElseThrow para evitar errores si el ID no existe en la BD
        return ProductoRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("No se encontró ningún producto con el ID: " + id));
    }

    public Producto crearProducto(Producto Producto) {
        return ProductoRepository.save(Producto);
    }

    public void eliminarProducto(Long id) {
        ProductoRepository.deleteById(id);
    }

    public Producto retirarProducto(Long idProducto, int cantidad) {
        Producto producto = ProductoRepository.findById(idProducto)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "El producto con ID " + idProducto + " no existe"));
    
            if (producto.getStock() < cantidad) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST, "Stock insuficiente. Stock actual: " + producto.getStock());
            }
        
            producto.setStock(producto.getStock() - cantidad);
            return ProductoRepository.save(producto);
    }
}
