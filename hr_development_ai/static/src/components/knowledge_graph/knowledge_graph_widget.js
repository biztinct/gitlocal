/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class KnowledgeGraphWidget extends Component {
    static template = "hr_development_ai.KnowledgeGraphWidget";
    static props = {
        ...standardFieldProps,
    };
    static supportedTypes = ["text"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.canvasRef = useRef("graphCanvas");

        this.state = useState({
            graphData: { nodes: [], edges: [] },
            isLoading: true,
            selectedNode: null,
            searchTerm: "",
        });

        // Force-directed layout state
        this.simulation = {
            nodes: [],
            edges: [],
            running: false,
            animationId: null,
        };

        // Canvas dimensions
        this.width = 800;
        this.height = 600;

        // Physics parameters
        this.physics = {
            repulsion: 100,
            attraction: 0.01,
            damping: 0.9,
            nodeRadius: 30,
        };

        onWillStart(async () => {
            await this.loadGraphData();
        });

        onMounted(() => {
            this.initializeCanvas();
            this.startSimulation();
        });

        onWillUnmount(() => {
            this.stopSimulation();
        });
    }

    /**
     * Load knowledge graph data from backend
     */
    async loadGraphData() {
        this.state.isLoading = true;
        try {
            const result = await this.orm.call(
                'hr.knowledge.node',
                'get_graph_data',
                []
            );

            this.state.graphData = result;
            this.initializeSimulation(result);
        } catch (error) {
            console.error('Error loading knowledge graph:', error);
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Initialize canvas and event listeners
     */
    initializeCanvas() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        const container = canvas.parentElement;
        this.width = container.clientWidth;
        this.height = Math.max(600, container.clientHeight);

        canvas.width = this.width;
        canvas.height = this.height;

        this.ctx = canvas.getContext('2d');

        // Add mouse event listeners
        canvas.addEventListener('click', this.onCanvasClick.bind(this));
        canvas.addEventListener('mousemove', this.onCanvasMouseMove.bind(this));
    }

    /**
     * Initialize force simulation
     */
    initializeSimulation(graphData) {
        // Create node objects with positions
        this.simulation.nodes = graphData.nodes.map((node, index) => {
            const angle = (index / graphData.nodes.length) * 2 * Math.PI;
            const radius = Math.min(this.width, this.height) / 3;

            return {
                ...node,
                x: this.width / 2 + radius * Math.cos(angle),
                y: this.height / 2 + radius * Math.sin(angle),
                vx: 0,
                vy: 0,
                isDragging: false,
            };
        });

        // Store edges
        this.simulation.edges = graphData.edges;
    }

    /**
     * Start force simulation
     */
    startSimulation() {
        this.simulation.running = true;
        this.animate();
    }

    /**
     * Stop force simulation
     */
    stopSimulation() {
        this.simulation.running = false;
        if (this.simulation.animationId) {
            cancelAnimationFrame(this.simulation.animationId);
        }
    }

    /**
     * Animation loop
     */
    animate() {
        if (!this.simulation.running) return;

        this.updateForces();
        this.render();

        this.simulation.animationId = requestAnimationFrame(() => this.animate());
    }

    /**
     * Update forces on nodes
     */
    updateForces() {
        const nodes = this.simulation.nodes;

        // Apply repulsion between all nodes
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const dx = nodes[j].x - nodes[i].x;
                const dy = nodes[j].y - nodes[i].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance > 0 && distance < 200) {
                    const force = this.physics.repulsion / (distance * distance);
                    const fx = (dx / distance) * force;
                    const fy = (dy / distance) * force;

                    nodes[i].vx -= fx;
                    nodes[i].vy -= fy;
                    nodes[j].vx += fx;
                    nodes[j].vy += fy;
                }
            }
        }

        // Apply attraction along edges
        for (const edge of this.simulation.edges) {
            const source = nodes.find(n => n.id === edge.source);
            const target = nodes.find(n => n.id === edge.target);

            if (source && target) {
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance > 0) {
                    const force = distance * this.physics.attraction;
                    const fx = (dx / distance) * force;
                    const fy = (dy / distance) * force;

                    source.vx += fx;
                    source.vy += fy;
                    target.vx -= fx;
                    target.vy -= fy;
                }
            }
        }

        // Update positions
        for (const node of nodes) {
            if (!node.isDragging) {
                node.x += node.vx;
                node.y += node.vy;
                node.vx *= this.physics.damping;
                node.vy *= this.physics.damping;

                // Keep nodes within bounds
                node.x = Math.max(this.physics.nodeRadius, Math.min(this.width - this.physics.nodeRadius, node.x));
                node.y = Math.max(this.physics.nodeRadius, Math.min(this.height - this.physics.nodeRadius, node.y));
            }
        }
    }

    /**
     * Render the graph
     */
    render() {
        if (!this.ctx) return;

        // Clear canvas
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Draw edges
        this.ctx.strokeStyle = '#D1D5DB';
        this.ctx.lineWidth = 2;

        for (const edge of this.simulation.edges) {
            const source = this.simulation.nodes.find(n => n.id === edge.source);
            const target = this.simulation.nodes.find(n => n.id === edge.target);

            if (source && target) {
                this.ctx.beginPath();
                this.ctx.moveTo(source.x, source.y);
                this.ctx.lineTo(target.x, target.y);
                this.ctx.stroke();
            }
        }

        // Draw nodes
        for (const node of this.simulation.nodes) {
            this.drawNode(node);
        }
    }

    /**
     * Draw a single node
     */
    drawNode(node) {
        const colors = {
            concept: '#7C3AED',
            resource: '#3B82F6',
            skill_category: '#10B981',
        };

        const color = colors[node.node_type] || '#6B7280';
        const isSelected = this.state.selectedNode && this.state.selectedNode.id === node.id;

        // Draw node circle
        this.ctx.beginPath();
        this.ctx.arc(node.x, node.y, this.physics.nodeRadius, 0, 2 * Math.PI);
        this.ctx.fillStyle = color;
        this.ctx.fill();

        if (isSelected) {
            this.ctx.strokeStyle = '#F59E0B';
            this.ctx.lineWidth = 4;
        } else {
            this.ctx.strokeStyle = '#FFFFFF';
            this.ctx.lineWidth = 2;
        }
        this.ctx.stroke();

        // Draw node label
        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.font = '12px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';

        const maxWidth = this.physics.nodeRadius * 1.8;
        const words = node.name.split(' ');
        let line = '';
        let y = node.y;

        for (let n = 0; n < words.length; n++) {
            const testLine = line + words[n] + ' ';
            const metrics = this.ctx.measureText(testLine);

            if (metrics.width > maxWidth && n > 0) {
                this.ctx.fillText(line, node.x, y);
                line = words[n] + ' ';
                y += 14;
            } else {
                line = testLine;
            }
        }
        this.ctx.fillText(line, node.x, y);
    }

    /**
     * Handle canvas click
     */
    onCanvasClick(event) {
        const rect = this.canvasRef.el.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Find clicked node
        for (const node of this.simulation.nodes) {
            const distance = Math.sqrt((node.x - x) ** 2 + (node.y - y) ** 2);
            if (distance < this.physics.nodeRadius) {
                this.state.selectedNode = node;
                this.openNodeDetail(node.id);
                return;
            }
        }

        // Clicked on empty space
        this.state.selectedNode = null;
    }

    /**
     * Handle mouse move
     */
    onCanvasMouseMove(event) {
        const rect = this.canvasRef.el.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Check if hovering over node
        let hovering = false;
        for (const node of this.simulation.nodes) {
            const distance = Math.sqrt((node.x - x) ** 2 + (node.y - y) ** 2);
            if (distance < this.physics.nodeRadius) {
                hovering = true;
                break;
            }
        }

        this.canvasRef.el.style.cursor = hovering ? 'pointer' : 'default';
    }

    /**
     * Open node detail view
     */
    async openNodeDetail(nodeId) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.knowledge.node',
            res_id: nodeId,
            views: [[false, 'form']],
            target: 'new',
        });
    }

    /**
     * Reset graph layout
     */
    resetLayout() {
        this.initializeSimulation(this.state.graphData);
    }
}

registry.category("fields").add("knowledge_graph", {
    component: KnowledgeGraphWidget,
});
