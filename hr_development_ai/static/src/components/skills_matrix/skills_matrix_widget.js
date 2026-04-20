/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class SkillsMatrixWidget extends Component {
    static template = "hr_development_ai.SkillsMatrixWidget";
    static props = {
        ...standardFieldProps,
    };
    static supportedTypes = ["text"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            matrixData: {
                categories: [],
                skills: []
            },
            isLoading: true,
        });

        onWillStart(async () => {
            await this.loadMatrixData();
        });
    }

    /**
     * Load skills matrix data from backend
     */
    async loadMatrixData() {
        this.state.isLoading = true;
        try {
            const result = await this.orm.call(
                'hr.employee',
                'get_skills_matrix_data',
                [this.props.record.resId]
            );

            this.state.matrixData = result;
        } catch (error) {
            console.error('Error loading skills matrix:', error);
            this.state.matrixData = {
                categories: [],
                skills: []
            };
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Get skills for a specific category
     */
    getSkillsForCategory(categoryName) {
        return this.state.matrixData.skills.filter(
            skill => skill.category === categoryName
        );
    }

    /**
     * Get skill level class for styling
     */
    getSkillLevelClass(skill) {
        const gap = skill.target_level - skill.current_level;

        if (gap <= 0) {
            return 'at-target'; // Green
        } else if (gap === 1) {
            return 'minor-gap'; // Yellow
        } else {
            return 'major-gap'; // Red
        }
    }

    /**
     * Generate array of dots for skill level visualization
     */
    getSkillDots(skill) {
        const dots = [];
        for (let i = 1; i <= 5; i++) {
            dots.push({
                index: i,
                filled: i <= skill.current_level,
                target: i === skill.target_level,
                isTarget: i <= skill.target_level
            });
        }
        return dots;
    }

    /**
     * Open skill detail view
     */
    async openSkillDetail(skillId) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee.skill',
            res_id: skillId,
            views: [[false, 'form']],
            target: 'new',
        });
    }

    /**
     * Get tooltip text for skill
     */
    getSkillTooltip(skill) {
        return `${skill.name}
Current Level: ${skill.current_level}/5
Target Level: ${skill.target_level}/5
Gap: ${skill.target_level - skill.current_level > 0 ? '+' + (skill.target_level - skill.current_level) : skill.target_level - skill.current_level}`;
    }

    /**
     * Get progress percentage
     */
    getProgressPercentage() {
        if (this.state.matrixData.skills.length === 0) {
            return 0;
        }

        const totalSkills = this.state.matrixData.skills.length;
        const atTargetSkills = this.state.matrixData.skills.filter(
            s => s.current_level >= s.target_level
        ).length;

        return Math.round((atTargetSkills / totalSkills) * 100);
    }

    /**
     * Get skills summary by gap level
     */
    getSkillsSummary() {
        const skills = this.state.matrixData.skills;
        return {
            at_target: skills.filter(s => s.current_level >= s.target_level).length,
            minor_gap: skills.filter(s => s.target_level - s.current_level === 1).length,
            major_gap: skills.filter(s => s.target_level - s.current_level > 1).length,
            total: skills.length
        };
    }
}

registry.category("fields").add("skills_matrix", {
    component: SkillsMatrixWidget,
});
