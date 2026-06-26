package rca.inventario.api_inventario.controllers;

import java.util.List;

import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import rca.inventario.api_inventario.models.Producto;
import rca.inventario.api_inventario.services.ProductoService;

@RestController
@RequestMapping("/inventario")
@RequiredArgsConstructor
public class InventarioController {

    private final ProductoService productoService;

    @GetMapping
    public List<Producto> obtenerTodosLosProductos() {
        return productoService.obtenerTodosLosProductos();
    }

    @GetMapping("/{id}")
    public Producto obtenerProductoPorId(@PathVariable Long id) {
        return productoService.obtenerProductoPorId(id);
    }

    @PostMapping
    public Producto crearProducto(@RequestBody @Valid Producto inventario) {
        // Al poner @Valid, Spring comprobará tus @NotBlank y @NotNull automáticamente
        return productoService.crearProducto(inventario);
    }

    @DeleteMapping("/{id}")
    public void eliminarProducto(@PathVariable Long id) {
        productoService.eliminarProducto(id);
    }

    @PostMapping("/{id}/retirar")
    public ResponseEntity<?> retirarProducto(@PathVariable Long id, @RequestParam int cantidad) {
        Producto productoActualizado = productoService.retirarProducto(id, cantidad);
        return ResponseEntity.ok(productoActualizado);
    }
}
